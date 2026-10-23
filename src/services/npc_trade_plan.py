"""Plan puro de compra/venta: stock, inventario y oro se calculan antes de persistir."""

from contextlib import suppress
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from src.models.item_constants import MAX_PLAYER_GOLD
from src.models.skills import skill_progress
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Snapshot
from src.utils.slot_plan import MAX_SLOT_QUANTITY, SlotPlan

if TYPE_CHECKING:
    from src.models.item import Item


def commerce_price(value: int, level: int, action: str) -> int:
    """Aplica regateo a la compra y conserva la venta al 50% del valor propio.

    Returns:
        Precio unitario entero: nunca se vende al NPC por más de lo que cuesta comprar.
    """
    level = max(0, min(100, level))
    return (value * 100 + 99 + level) // (100 + level) if action == "buy" else value // 2


@dataclass(frozen=True, slots=True)
class NpcTradeRequest:
    """Petición de recursos sin precio suministrado por el cliente."""

    user_id: int
    npc_id: int
    slot: int
    quantity: int
    action: Literal["buy", "sell"]


class NpcTradePlan:
    """Copia de recursos que sólo se convierte en writes si pasa todas las reglas."""

    def __init__(
        self,
        snapshot: Snapshot,
        request: NpcTradeRequest,
        capacity: int,
        inventory_stack: int,
        merchant_capacity: int,
        allowed_types: frozenset[int] | None = None,
    ) -> None:
        """Carga valores observados bajo WATCH sin hacer I/O."""
        self.request = request
        self.allowed_types = allowed_types
        self.inventory_key = RedisKeys.player_inventory(request.user_id)
        self.stock_key = RedisKeys.merchant_inventory(request.npc_id)
        self.index_key = f"merchant:{request.npc_id}:items"
        self.item_index = cast("set[str]", snapshot.get(self.index_key) or set())
        self.stats_key = RedisKeys.player_user_stats(request.user_id)
        self.inventory = SlotPlan(
            cast("dict[str, str]", snapshot[self.inventory_key]), capacity, inventory_stack
        )
        self.stock = SlotPlan(
            cast("dict[str, str]", snapshot[self.stock_key]), merchant_capacity, MAX_SLOT_QUANTITY
        )
        self.equipment = cast(
            "dict[str, str]", snapshot[RedisKeys.player_equipment(request.user_id)]
        )
        self.gold = int(cast("dict[str, str]", snapshot[self.stats_key]).get("gold", 0))
        skills = cast("dict[str, str]", snapshot.get(RedisKeys.player_skills(request.user_id), {}))
        self.commerce_level = next(
            p.level for p in skill_progress(skills) if p.definition.key == "comerciar"
        )

    def source_item_id(self) -> int:
        """Obtiene la identidad actual del slot fuente.

        Returns:
            Identificador del objeto actual o cero si no existe.
        """
        source = self.stock if self.request.action == "buy" else self.inventory
        stack = source.slots.get(self.request.slot)
        return stack.item_id if stack else 0

    def decide(self, catalog: dict[int, Item], expected_item_id: int) -> Decision:
        """Calcula los tres recursos o un rechazo sin writes de negocio.

        Returns:
            Resultado y campos a confirmar en un único EXEC.
        """
        item = catalog.get(self.source_item_id())
        if item is None or self.source_item_id() != expected_item_id:
            return Decision(
                {"applied": False, "message": "El objeto del slot ya no está disponible"}, {}
            )
        if type(item.value) is not int or item.value <= 0:
            return Decision({"applied": False, "message": "Este objeto no se puede comerciar"}, {})
        if (
            self.request.action == "sell"
            and self.allowed_types is not None
            and item.obj_type not in self.allowed_types
        ):
            return Decision(
                {"applied": False, "message": "Este comerciante no compra ese tipo de objeto."}, {}
            )
        if not 0 <= self.gold <= MAX_PLAYER_GOLD:
            return Decision({"applied": False, "message": "Saldo persistido fuera de rango"}, {})
        try:
            total = (
                commerce_price(item.value, self.commerce_level, self.request.action)
                * self.request.quantity
            )
            if self.request.action == "buy":
                self._buy(item.item_id, total)
            else:
                self._sell(item.item_id, total)
        except ValueError as error:
            return Decision({"applied": False, "message": str(error)}, {})
        verb = "comprado" if self.request.action == "buy" else "vendido"
        result = {
            "applied": True,
            "gold": self.gold,
            "total": total,
            "message": f"Has {verb} {self.request.quantity}x {item.name} por {total} oro",
        }
        return Decision(
            result,
            {
                self.inventory_key: self.inventory.fields(),
                self.stock_key: self.stock.fields(),
                self.index_key: self.item_index
                | {str(stack.item_id) for stack in self.stock.slots.values()},
                self.stats_key: {"gold": str(self.gold)},
            },
        )

    def _buy(self, item_id: int, total: int) -> None:
        """Calcula stock y débito después de comprobar fondos y espacio completo.

        Raises:
            ValueError: Si el comprador no puede pagar o recibir la compra completa.
        """
        if total > self.gold:
            msg = f"No tienes suficiente oro. Necesitas {total} oro."
            raise ValueError(msg)
        removed = self.stock.take(self.request.slot, item_id, self.request.quantity)
        self.inventory.give(item_id, self.request.quantity, instance_ids=removed.instance_ids)
        self.gold -= total

    def _sell(self, item_id: int, total: int) -> None:
        """Calcula retiro y pago exacto; el excedente no se descarta al llegar al tope.

        Raises:
            ValueError: Si el precio es cero, hay equipo o el pago excede el máximo.
        """
        if total < 1 or total > MAX_PLAYER_GOLD - self.gold:
            msg = "El pago no es válido o supera el límite de oro"
            raise ValueError(msg)
        if str(self.request.slot) in self.equipment.values():
            msg = "Desequipá el objeto antes de venderlo"
            raise ValueError(msg)
        removed = self.inventory.take(self.request.slot, item_id, self.request.quantity)
        self.gold += total
        # Regla previa: el NPC compra aunque no guarde más stock para revender.
        with suppress(ValueError):
            self.stock.give(item_id, self.request.quantity, instance_ids=removed.instance_ids)
