"""Pickup conjunto de suelo e inventario/oro, sin claim ni compensación en memoria."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.pickup_command import PickupCommand
from src.config.config_manager import ConfigManager
from src.models.item_constants import GOLD_ITEM_ID
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.services.inventory_notifications import notify_inventory

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)


class PickupCommandHandler(CommandHandler):
    """Recoge una identidad estable y notifica sólo después del commit durable."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        item_catalog: ItemCatalog | None,
        party_service: PartyService | None,
        message_sender: MessageSender,
    ) -> None:
        """Conserva los servicios de la sesión y el contrato propio de pickup libre."""
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.item_catalog = item_catalog
        self.party_service = party_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Confirma origen e ingreso juntos sin retirar primero del índice local.

        Returns:
            Resultado confirmado o rechazo sin recursos perdidos.
        """
        if not isinstance(command, PickupCommand):
            return CommandResult.error("Comando inválido")
        try:
            if command.origin is None:
                position = await self.player_repo.get_position(command.user_id)
                if not position:
                    return CommandResult.error("No se pudo obtener la posición del jugador")
                command.origin = position["map"], position["x"], position["y"]
            map_id, x, y = command.origin
            if command.expected_stack_id is None:
                await self.map_manager.load_ground_items(map_id)
                tile = self.map_manager.get_ground_items(map_id, x, y)
                command.expected_stack_id = str(tile[0].get("stack_id", "")) if tile else ""
                command.expected_item_id = int(tile[0].get("item_id") or 0) if tile else 0
            if command.expected_item_id and command.expected_item_id != GOLD_ITEM_ID:
                if self.inventory_repo is None or self.item_catalog is None:
                    return CommandResult.error("Servicios no disponibles para recoger objetos")
                if not self.item_catalog.get_item_data(command.expected_item_id):
                    return CommandResult.error("Objeto no encontrado en catálogo")
            request = GroundRequest(
                command.user_id, map_id, x, y, "pickup", expected_stack=command.expected_stack_id
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
            if result["type"] == "gold":
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
            await self.message_sender.send_console_msg(f"Recogiste {result['quantity']} {label}.")
            if result.get("devaluation_loss", 0):
                await self.message_sender.send_console_msg(
                    f"Devaluación acumulada: desaparecieron {result['devaluation_loss']} "
                    "monedas de oro."
                )
            command.notified = True
            return CommandResult.ok(data=result)
        except Exception:
            logger.exception("No se pudo confirmar el pickup")
            return CommandResult.error(
                "No se pudo confirmar la operación; revisá el inventario al reconectar."
            )
