"""Handler para comando de movimiento."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.walk_movement_handler import WalkMovementHandler
from src.command_handlers.walk_validation_handler import WalkValidationHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.walk_command import WalkCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.map.player_map_service import PlayerMapService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)


class WalkCommandHandler(CommandHandler):
    """Handler para comando de movimiento (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        broadcast_service: MultiplayerBroadcastService | None,
        stamina_service: StaminaService | None,
        player_map_service: PlayerMapService | None,
        inventory_repo: InventoryRepository | None,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            stamina_service: Servicio de stamina.
            player_map_service: Servicio de transición de mapas.
            inventory_repo: Repositorio de inventario.
            map_resources: Servicio de recursos de mapa.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.message_sender = message_sender

        # Inicializar handlers especializados
        self.validation_handler = WalkValidationHandler(
            player_repo=player_repo,
            stamina_service=stamina_service,
            message_sender=message_sender,
        )

        self.movement_handler = WalkMovementHandler(
            player_repo=player_repo,
            map_manager=map_manager,
            broadcast_service=broadcast_service,
            player_map_service=player_map_service,
            inventory_repo=inventory_repo,
            map_resources=map_resources,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de movimiento (solo lógica de negocio).

        Args:
            command: Comando de movimiento.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, WalkCommand):
            return CommandResult.error("Comando inválido: se esperaba WalkCommand")

        user_id = command.user_id
        heading = command.heading

        logger.debug(
            "WalkCommandHandler: Procesando movimiento user_id=%d heading=%d", user_id, heading
        )

        # Validar movimiento
        can_move, error_msg = await self.validation_handler.validate_movement(user_id)
        if not can_move:
            return CommandResult.error(error_msg or "No se puede mover")

        # Obtener posición actual
        if not self.player_repo:
            logger.error("PlayerRepository no está disponible para movimiento")
            return CommandResult.error("Error interno: repositorio no disponible")

        position = await self.player_repo.get_position(user_id)
        if position is None:
            logger.warning("No se encontró posición para user_id %d", user_id)
            return CommandResult.error("Posición no encontrada")

        current_x = position["x"]
        current_y = position["y"]
        current_map = position["map"]

        # Ejecutar movimiento
        success, error_msg, data = await self.movement_handler.execute_movement(
            user_id, heading, current_x, current_y, current_map
        )

        if success:
            return CommandResult.ok(data=data)
        return CommandResult.error(error_msg or "Error al ejecutar movimiento")
