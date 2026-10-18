"""Sincroniza slots confirmados sin crear objetos ni modificar inventarios."""

from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager
from src.models.items_catalog import ITEMS_CATALOG
from src.utils.inventory_slot import InventorySlot
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.inventory_repository import InventoryRepository


async def notify_inventory(sender: MessageSender, repo: InventoryRepository, user_id: int) -> None:
    """Envía los treinta slots actuales, incluidos vacíos y equipo existente."""
    inventory = await repo.get_inventory(user_id)
    equipment = await repo.redis_client.hgetall(RedisKeys.player_equipment(user_id))
    for slot in range(1, ConfigManager.as_int(repo.MAX_SLOTS) + 1):
        stack = InventorySlot.parse(inventory.get(f"slot_{slot}", ""))
        item = ITEMS_CATALOG.get(stack.item_id) if stack else None
        await sender.send_change_inventory_slot(
            slot=slot,
            item_id=item.item_id if item else 0,
            name=item.name if item else "",
            amount=stack.quantity if stack and item else 0,
            equipped=str(slot) in equipment.values(),
            grh_id=item.graphic_id if item else 0,
            item_type=item.item_type.to_client_type() if item else 0,
            max_hit=(item.max_damage or 0) if item else 0,
            min_hit=(item.min_damage or 0) if item else 0,
            max_def=(item.defense or 0) if item else 0,
            min_def=(item.defense or 0) if item else 0,
            sale_price=float(item.value) if item else 0.0,
        )


async def notify_bank(sender: MessageSender, repo: BankRepository, user_id: int) -> None:
    """Sincroniza también los slots vacíos de la bóveda confirmada."""
    values = await repo.get_bank(user_id)
    for slot in range(1, ConfigManager.as_int(repo.MAX_SLOTS) + 1):
        stack = InventorySlot.parse(values.get(f"slot_{slot}", ""))
        item = ITEMS_CATALOG.get(stack.item_id) if stack else None
        await sender.send_change_bank_slot(
            slot=slot,
            item_id=item.item_id if item else 0,
            name=item.name if item else "",
            amount=stack.quantity if stack and item else 0,
            grh_id=item.graphic_id if item else 0,
            item_type=item.item_type.to_client_type() if item else 0,
            max_hit=(item.max_damage or 0) if item else 0,
            min_hit=(item.min_damage or 0) if item else 0,
            max_def=(item.defense or 0) if item else 0,
            min_def=(item.defense or 0) if item else 0,
        )
