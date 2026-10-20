"""Transferencias entre suelo persistido, inventario y oro en un commit recuperable."""

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Literal, cast

from src.economy.ground_devaluation import split_remainder
from src.economy.tax_transactions import tax_key
from src.economy.taxes import BASIS_POINTS
from src.models.item_constants import GOLD_ITEM_ID, MAX_PLAYER_GOLD
from src.utils.durability import require_durable
from src.utils.ground_state import (
    GROUND_TTL_SECONDS,
    MAX_GROUND_COORDINATE,
    MAX_GROUND_MAP_ID,
    GroundItem,
    GroundState,
    stack_identity,
)
from src.utils.ground_storage import position_fields
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from redis.asyncio import Redis


@dataclass(frozen=True, slots=True)
class GroundRequest:
    """Identidad de la acción y posición que debe seguir siendo válida en el commit."""

    user_id: int
    map_id: int
    x: int
    y: int
    action: Literal["pickup", "drop_item", "drop_gold"]
    slot: int = 0
    quantity: int = 0
    expected_stack: str = ""
    allow_dead: bool = False
    expected_item_id: int = 0
    graphic_id: int | None = None


class GroundTransferPlan:
    """Plan conjunto; las copias no se publican hasta confirmar AOF."""

    def __init__(
        self,
        snapshot: Snapshot,
        request: GroundRequest,
        identity: str,
        capacity: int,
        max_stack: int,
    ) -> None:
        """Carga recursos observados por WATCH."""
        self.request = request
        self.identity = identity
        self.ground_key = RedisKeys.ground_items(request.map_id)
        self.inventory_key = RedisKeys.player_inventory(request.user_id)
        self.stats_key = RedisKeys.player_user_stats(request.user_id)
        self.equipment_key = RedisKeys.player_equipment(request.user_id)
        self.ground = GroundState(request.map_id, cast("str | None", snapshot[self.ground_key]))
        self.inventory = SlotPlan(
            cast("dict[str, str]", snapshot[self.inventory_key]), capacity, max_stack
        )
        self.stats = cast("dict[str, str]", snapshot[self.stats_key])
        self.equipment = cast("dict[str, str]", snapshot[self.equipment_key]).copy()
        self.position = cast("dict[str, str]", snapshot[RedisKeys.player_position(request.user_id)])
        self.gold = int(self.stats.get("gold", 0))
        self.tax_state = cast("dict[str, str]", snapshot.get(tax_key(request.user_id)) or {})
        self.bank_gold = int(str(snapshot.get(RedisKeys.bank_gold(request.user_id)) or 0))
        self.devaluation_fields: dict[str, str] = {}
        self.devaluation_loss = 0

    def apply(self) -> Decision:
        """Calcula la transferencia conservando todos los campos ajenos.

        Returns:
            Resultado efectivo y recursos a confirmar juntos.

        Raises:
            ValueError: Ante posición cambiada, estado inválido o recursos insuficientes.
        """
        if any(
            int(self.position.get(field, -1)) != expected
            for field, expected in (
                ("map", self.request.map_id),
                ("x", self.request.x),
                ("y", self.request.y),
            )
        ):
            msg = "La posición cambió; intentá nuevamente"
            raise ValueError(msg)
        if (
            not self.request.allow_dead
            and "min_hp" in self.stats
            and int(self.stats["min_hp"]) <= 0
        ):
            msg = "No podés recoger ni tirar objetos estando muerto"
            raise ValueError(msg)
        if not 0 <= self.gold <= MAX_PLAYER_GOLD:
            msg = "Saldo persistido fuera de rango"
            raise ValueError(msg)
        item = self._pickup() if self.request.action == "pickup" else self._drop()
        writes: dict[str, str | dict[str, str]] = {
            self.ground_key: self.ground.encode(),
            self.inventory_key: self.inventory.fields(),
            self.stats_key: {"gold": str(self.gold)},
            self.equipment_key: self.equipment,
        }
        if self.devaluation_fields:
            writes[tax_key(self.request.user_id)] = self.devaluation_fields
        return Decision(
            {
                "applied": True,
                "item": item,
                "quantity": item["quantity"],
                "type": "gold" if item["item_id"] == GOLD_ITEM_ID else "item",
                "item_id": item["item_id"],
                "devaluation_loss": self.devaluation_loss,
            },
            writes,
        )

    def _pickup(self) -> GroundItem:
        """Retira por identidad estable y acredita la cantidad completa o remanente de oro.

        Returns:
            Cantidad transferida, preservando la identidad del remanente.

        Raises:
            ValueError: Si no existe el stack o no puede aceptarse su contenido.
        """
        tile = self.ground.tile(self.request.x, self.request.y)
        item = next((row for row in tile if row["stack_id"] == self.request.expected_stack), None)
        if item is None:
            msg = "No hay nada aquí o el objeto cambió"
            raise ValueError(msg)
        transferred = item.copy()
        amount = cast("int", item["quantity"])
        if item["item_id"] == GOLD_ITEM_ID:
            accepted = min(amount, MAX_PLAYER_GOLD - self.gold)
            if accepted < 1:
                msg = "No podés cargar más oro"
                raise ValueError(msg)
            if self.tax_state:
                split = split_remainder(
                    cast("int", item.get("devaluation_remainder", 0)), accepted, amount
                )
                self.devaluation_loss, remainder = divmod(
                    int(self.tax_state.get("remainder", 0)) + split.moved, BASIS_POINTS
                )
                self.devaluation_fields = {"remainder": str(remainder)}
                if self.devaluation_loss:
                    self.devaluation_fields["total_paid"] = str(
                        int(self.tax_state.get("total_paid", 0)) + self.devaluation_loss
                    )
                item["devaluation_remainder"] = split.remaining
                transferred["devaluation_remainder"] = split.moved
            self.gold += accepted - self.devaluation_loss
            transferred["quantity"] = accepted
            if accepted < amount:
                item["quantity"] = amount - accepted
                return transferred
        else:
            self.inventory.give(cast("int", item["item_id"]), amount)
        tile.remove(item)
        return transferred

    def _drop(self) -> GroundItem:
        """Retira saldo/slot y crea el stack dentro del mismo plan.

        Returns:
            Stack identificado con la cantidad efectivamente retirada.

        Raises:
            ValueError: Ante cantidad inválida, slot vacío o equipo no desequipado.
        """
        if type(self.request.quantity) is not int or self.request.quantity < 1:
            msg = "Cantidad inválida"
            raise ValueError(msg)
        fraction = 0
        if self.request.action == "drop_gold":
            amount = min(self.request.quantity, self.gold)
            if amount < 1:
                msg = "No tienes oro para tirar"
                raise ValueError(msg)
            if self.tax_state:
                remainder = int(self.tax_state.get("remainder", 0))
                split = split_remainder(remainder, amount, self.gold + self.bank_gold)
                fraction = split.moved
                self.devaluation_fields = {"remainder": str(split.remaining)}
            self.gold -= amount
            item_id = GOLD_ITEM_ID
        else:
            stack = self.inventory.slots.get(self.request.slot)
            if stack is None or stack.item_id != self.request.expected_item_id:
                msg = "No hay ningún objeto en ese slot"
                raise ValueError(msg)
            if str(self.request.slot) in self.equipment.values():
                if not self.request.allow_dead:
                    msg = "Desequipá el objeto antes de tirarlo"
                    raise ValueError(msg)
                self.equipment = {
                    field: "0" if value == str(self.request.slot) else value
                    for field, value in self.equipment.items()
                }
            amount = min(self.request.quantity, stack.quantity)
            item_id = stack.item_id
            self.inventory.take(self.request.slot, item_id, amount)
        item: GroundItem = {
            "item_id": item_id,
            "quantity": amount,
            "stack_id": stack_identity(self.identity),
            "owner_id": None,
            "spawn_time": None,
            "grh_index": self.request.graphic_id,
        }
        if item_id == GOLD_ITEM_ID and self.tax_state:
            item["devaluation_remainder"] = fraction
        self.ground.append(self.request.x, self.request.y, item)
        return item


async def transfer_ground(
    redis: Redis, request: GroundRequest, identity: str, capacity: int = 30, max_stack: int = 20
) -> dict[str, Any]:
    """Confirma suelo y recursos del jugador, y exige AOF antes de notificar.

    Returns:
        Resultado recuperable mediante la misma petición e identidad.

    Raises:
        ValueError: Ante identidad, posición o acción inválidas.
    """
    if (
        not 1 <= request.map_id <= MAX_GROUND_MAP_ID
        or not 1 <= request.x <= MAX_GROUND_COORDINATE
        or not 1 <= request.y <= MAX_GROUND_COORDINATE
    ):
        msg = "Posición del suelo inválida"
        raise ValueError(msg)
    if request.action not in {"pickup", "drop_item", "drop_gold"}:
        msg = "Acción de suelo inválida"
        raise ValueError(msg)

    def decide(snapshot: Snapshot) -> Decision:
        try:
            plan = GroundTransferPlan(snapshot, request, identity, capacity, max_stack)
            return plan.apply()
        except (ValueError, TypeError) as error:
            return Decision({"applied": False, "error": str(error)}, {})

    keys = (
        RedisKeys.player_inventory(request.user_id),
        RedisKeys.player_user_stats(request.user_id),
        RedisKeys.player_equipment(request.user_id),
        RedisKeys.player_position(request.user_id),
    )
    resources = (
        *tuple(Resource(key, "hash") for key in keys),
        Resource(
            RedisKeys.ground_items(request.map_id),
            "ground",
            GROUND_TTL_SECONDS,
            fields=position_fields(((request.x, request.y),)),
        ),
    )
    await require_durable(redis)
    result = await transact(redis, resources, identity, asdict(request), decide)
    await require_durable(redis)
    return result
