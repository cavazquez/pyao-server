"""Comercio NPC con precio del servidor y commit conjunto de todos los recursos."""

from dataclasses import asdict
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager
from src.services.npc_trade_plan import NpcTradePlan, NpcTradeRequest, commerce_price
from src.services.skill_training import trained_decision, training_resources
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id as new_operation_id
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import MAX_SLOT_QUANTITY

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.item import Item
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.merchant_repository import MerchantRepository
    from src.repositories.player_repository import PlayerRepository


class CommerceService:
    """Compra y venta indivisibles, con recibo identificado para reintentos inciertos."""

    def __init__(
        self,
        inventory_repo: InventoryRepository,
        merchant_repo: MerchantRepository,
        item_catalog: dict[int, Item],
        player_repo: PlayerRepository,
    ) -> None:
        """Conserva repositorios concretos y el catálogo autoritativo del servidor."""
        self.inventory_repo = inventory_repo
        self.merchant_repo = merchant_repo
        self.items_catalog = item_catalog
        self.player_repo = player_repo

    async def buy_item(
        self,
        user_id: int,
        npc_id: int,
        slot: int,
        quantity: int,
        *,
        operation_id: str | None = None,
    ) -> tuple[bool, str]:
        """Compra stock y entrega stacks con un débito indivisible.

        Returns:
            Éxito y mensaje del resultado confirmado.
        """
        return await self._trade(
            NpcTradeRequest(user_id, npc_id, slot, quantity, "buy"), operation_id
        )

    async def sell_item(
        self,
        user_id: int,
        npc_id: int,
        slot: int,
        quantity: int,
        *,
        operation_id: str | None = None,
    ) -> tuple[bool, str]:
        """Retira objetos y acredita (valor // 2) por cantidad sin truncar el pago.

        Returns:
            Éxito y mensaje del resultado confirmado.
        """
        return await self._trade(
            NpcTradeRequest(user_id, npc_id, slot, quantity, "sell"), operation_id
        )

    async def _trade(self, request: NpcTradeRequest, identity: str | None) -> tuple[bool, str]:
        """Planifica y confirma tres recursos con AOF y un recibo estable.

        Returns:
            Resultado confirmado o rechazo sin modificar recursos.
        """
        capacity = ConfigManager.as_int(self.inventory_repo.MAX_SLOTS)
        source_capacity = self.merchant_repo.MAX_SLOTS if request.action == "buy" else capacity
        if type(request.quantity) is not int or not 1 <= request.quantity <= MAX_SLOT_QUANTITY:
            return False, "Cantidad inválida"
        if not 1 <= request.slot <= source_capacity or request.user_id < 1 or request.npc_id < 1:
            return False, "Slot o comerciante inválidos"
        expected_item: int | None = None

        def decide(snapshot: Snapshot) -> Decision:
            nonlocal expected_item
            try:
                plan = NpcTradePlan(
                    snapshot,
                    request,
                    capacity,
                    self.inventory_repo.stacking.max_stack,
                    self.merchant_repo.MAX_SLOTS,
                )
            except ValueError as error:
                return Decision({"applied": False, "message": str(error)}, {})
            if expected_item is None:
                expected_item = plan.source_item_id()
            decision = plan.decide(self.items_catalog, expected_item)
            return (
                trained_decision(decision, snapshot, request.user_id, (("comerciar", True),))
                if decision.result["applied"]
                else decision
            )

        resources = tuple(
            Resource(key, "hash")
            for key in (
                RedisKeys.player_inventory(request.user_id),
                RedisKeys.player_user_stats(request.user_id),
                RedisKeys.player_equipment(request.user_id),
                RedisKeys.merchant_inventory(request.npc_id),
            )
        )
        resources = tuple(
            {r.key: r for r in (*resources, *training_resources(request.user_id))}.values()
        )
        redis = self.player_repo.redis.redis
        await require_durable(redis)
        result = await transact(
            redis, resources, identity or new_operation_id(), asdict(request), decide
        )
        await require_durable(redis)
        return bool(result["applied"]), str(result["message"])

    async def notify_merchant(self, sender: MessageSender, npc_id: int, user_id: int = 0) -> None:
        """Actualiza el stock confirmado también cuando la compra fue rechazada."""
        inventory = await self.merchant_repo.get_inventory(npc_id)
        skills = await self.player_repo.get_skills(user_id) if user_id else None
        level = skills.get("comerciar", 0) if skills else 0
        for slot in range(1, self.merchant_repo.MAX_SLOTS + 1):
            raw = inventory.get(f"slot_{slot}", "")
            stack = InventorySlot.parse(str(raw))
            item = self.items_catalog.get(stack.item_id) if stack else None
            await sender.send_change_npc_inventory_slot(
                slot=slot,
                name=item.name if item else "",
                amount=stack.quantity if stack and item else 0,
                sale_price=float(commerce_price(item.value, level, "buy")) if item else 0.0,
                grh_id=item.graphic_id if item else 0,
                item_id=item.item_id if item else 0,
                item_type=item.item_type.to_client_type() if item else 0,
                max_hit=(item.max_damage or 0) if item else 0,
                min_hit=(item.min_damage or 0) if item else 0,
                max_def=(item.defense or 0) if item else 0,
                min_def=(item.defense or 0) if item else 0,
            )
