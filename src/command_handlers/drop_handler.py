"""Drop identificado con transferencia conjunta de inventario/oro al suelo persistido."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.drop_command import DropCommand
from src.config.config_manager import ConfigManager
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.services.inventory_notifications import notify_inventory

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)
GOLD_SLOT_CLASSIC = 0
GOLD_SLOT_GODOT = 31


class DropCommandHandler(CommandHandler):
    """Conserva los slots clásicos/Godot y espera un resultado confirmado antes de notificar."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
        item_catalog: ItemCatalog | None = None,
    ) -> None:
        """Conserva las dependencias de la sesión."""
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.message_sender = message_sender
        self.item_catalog = item_catalog

    async def handle(self, command: Command) -> CommandResult:
        """Confirma el stack y el débito en un EXEC, sin persistir snapshots de caché.

        Returns:
            Cantidad efectiva confirmada o rechazo sin debitar recursos.
        """
        if not isinstance(command, DropCommand):
            return CommandResult.error("Comando inválido")
        if command.quantity < 1:
            return CommandResult.error("Cantidad inválida")
        gold = command.slot <= GOLD_SLOT_CLASSIC or command.slot == GOLD_SLOT_GODOT
        try:
            if command.origin is None:
                position = await self.player_repo.get_position(command.user_id)
                if not position:
                    return CommandResult.error("No se pudo obtener la posición del jugador")
                command.origin = position["map"], position["x"], position["y"]
            if not gold:
                if self.inventory_repo is None:
                    return CommandResult.error("Repositorio de inventario no disponible")
                if command.expected_item_id is None:
                    source = await self.inventory_repo.get_slot(command.user_id, command.slot)
                    command.expected_item_id = source[0] if source else 0
                if not command.expected_item_id:
                    return CommandResult.error("No hay nada en ese slot")
            map_id, x, y = command.origin
            request = GroundRequest(
                command.user_id,
                map_id,
                x,
                y,
                "drop_gold" if gold else "drop_item",
                slot=command.slot,
                quantity=command.quantity,
                expected_item_id=command.expected_item_id or 0,
                graphic_id=(
                    self.item_catalog.get_grh_index(command.expected_item_id or 0)
                    if self.item_catalog and not gold
                    else None
                ),
            )
            capacity = (
                ConfigManager.as_int(self.inventory_repo.MAX_SLOTS) if self.inventory_repo else 30
            )
            max_stack = self.inventory_repo.stacking.max_stack if self.inventory_repo else 20
            result = await self.map_manager.apply_ground_operation(
                map_id,
                x,
                y,
                self.player_repo.redis.redis,
                lambda: transfer_ground(
                    self.player_repo.redis.redis, request, command.operation_id, capacity, max_stack
                ),
                broadcast_service=self.broadcast_service,
                operation_id=command.operation_id,
            )
            if not result["applied"]:
                await self.message_sender.send_console_msg(result["error"])
                return CommandResult.error(result["error"])
            if command.notified:
                return CommandResult.ok(data=result)
            if gold:
                await self.message_sender.send_update_user_stats_from_repo(
                    command.user_id, self.player_repo
                )
                label = "monedas de oro"
            else:
                if self.inventory_repo:
                    await notify_inventory(
                        self.message_sender, self.inventory_repo, command.user_id
                    )
                label = (
                    (self.item_catalog.get_item_name(result["item_id"]) or "objeto")
                    if self.item_catalog
                    else "objeto"
                )
            await self.message_sender.send_console_msg(f"Tiraste {result['quantity']} {label}.")
            command.notified = True
            return CommandResult.ok(data=result)
        except Exception:
            logger.exception("No se pudo confirmar el drop")
            return CommandResult.error(
                "No se pudo confirmar la operación; revisá el inventario al reconectar."
            )
