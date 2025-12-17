"""Handler para comando de doble click (items del inventario o NPCs)."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.double_click_item_handler import DoubleClickItemHandler
from src.command_handlers.double_click_npc_handler import DoubleClickNPCHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.double_click_command import DoubleClickCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class DoubleClickCommandHandler(CommandHandler):
    """Handler para comando de doble click (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

        # Inicializar handlers especializados
        self.item_handler = DoubleClickItemHandler(
            player_repo=player_repo,
            message_sender=message_sender,
        )

        self.npc_handler = DoubleClickNPCHandler(
            map_manager=map_manager,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de doble click (solo lógica de negocio).

        Args:
            command: Comando de doble click.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, DoubleClickCommand):
            return CommandResult.error("Comando inválido: se esperaba DoubleClickCommand")

        user_id = command.user_id
        target = command.target

        logger.info(
            "DoubleClickCommandHandler: user_id=%d hace doble click en target=%d",
            user_id,
            target,
        )

        try:
            # Si el target es > MAX_INVENTORY_SLOT, probablemente es un CharIndex de NPC
            if command.is_npc_click():
                success, error_msg, data = await self.npc_handler.handle_npc_double_click(
                    user_id, target, command.map_id
                )
                if success:
                    return CommandResult.ok(data=data)
                return CommandResult.error(error_msg or "Error al interactuar con NPC")

            success, error_msg, data = await self.item_handler.handle_item_use(user_id, target)
            if success:
                return CommandResult.ok(data=data)
            return CommandResult.error(error_msg or "Error al usar item")

        except Exception as e:
            logger.exception("Error procesando DOUBLE_CLICK")
            return CommandResult.error(f"Error al procesar doble click: {e!s}")
