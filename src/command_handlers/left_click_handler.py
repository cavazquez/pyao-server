"""Handler para comando de click izquierdo en el mapa."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.left_click_npc_handler import LeftClickNPCHandler
from src.command_handlers.left_click_tile_handler import LeftClickTileHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.left_click_command import LeftClickCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.door_repository import DoorRepository
    from src.repositories.merchant_repository import MerchantRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.door_service import DoorService
    from src.services.map.map_resources_service import MapResourcesService
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class LeftClickCommandHandler(CommandHandler):
    """Handler para comando de click izquierdo (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        map_resources: MapResourcesService | None,
        bank_repo: BankRepository | None,
        merchant_repo: MerchantRepository | None,
        door_service: DoorService | None,
        door_repo: DoorRepository | None,
        redis_client: RedisClient | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            map_resources: Servicio de recursos del mapa.
            bank_repo: Repositorio de banco.
            merchant_repo: Repositorio de mercaderes.
            door_service: Servicio de puertas.
            door_repo: Repositorio de puertas.
            redis_client: Cliente Redis.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

        # Inicializar handlers especializados
        self.npc_handler = LeftClickNPCHandler(
            merchant_repo=merchant_repo,
            bank_repo=bank_repo,
            redis_client=redis_client,
            message_sender=message_sender,
        )

        self.tile_handler = LeftClickTileHandler(
            map_manager=map_manager,
            map_resources=map_resources,
            door_service=door_service,
            door_repo=door_repo,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de click izquierdo (solo lógica de negocio).

        Args:
            command: Comando de click izquierdo.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, LeftClickCommand):
            return CommandResult.error("Comando inválido: se esperaba LeftClickCommand")

        user_id = command.user_id
        map_id = command.map_id
        x = command.x
        y = command.y

        logger.info(
            "LeftClickCommandHandler: user_id=%d hace click en mapa=%d, posición=(%d, %d)",
            user_id,
            map_id,
            x,
            y,
        )

        if not self.map_manager:
            logger.error("MapManager no disponible para click")
            return CommandResult.error("Error interno: gestor de mapas no disponible")

        try:
            # Buscar NPC en esa posición
            all_npcs = self.map_manager.get_npcs_in_map(map_id)
            npc_found = None
            for npc in all_npcs:
                if npc.x == x and npc.y == y:
                    npc_found = npc
                    break

            if npc_found:
                success, error_msg, data = await self.npc_handler.handle_npc_click(
                    user_id, npc_found
                )
                if success:
                    return CommandResult.ok(data=data)
                return CommandResult.error(error_msg or "Error al procesar click en NPC")

            # No hay NPC, mostrar información del tile
            success, error_msg, data = await self.tile_handler.handle_tile_click(map_id, x, y)
            if success:
                return CommandResult.ok(data=data)
            return CommandResult.error(error_msg or "Error al procesar click en tile")

        except Exception as e:
            logger.exception("Error procesando LEFT_CLICK")
            return CommandResult.error(f"Error al procesar click: {e!s}")
