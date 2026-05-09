"""Handler para comando de togglear modo seguro."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.safe_toggle_command import SafeToggleCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class SafeToggleCommandHandler(CommandHandler):
    """Handler para comando de togglear modo seguro (anti-PvP)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Maneja el comando de togglear modo seguro.

        Args:
            command: Comando a procesar.

        Returns:
            Resultado del comando.
        """
        if not isinstance(command, SafeToggleCommand):
            return CommandResult.error("Comando inválido: se esperaba SafeToggleCommand")

        user_id = command.user_id
        current_safe_mode = await self.player_repo.get_safe_mode(user_id)
        new_safe_mode = not current_safe_mode
        await self.player_repo.set_safe_mode(user_id, new_safe_mode)

        status_text = "ACTIVADO" if new_safe_mode else "DESACTIVADO"
        await self.message_sender.send_console_msg(
            f"Modo seguro {status_text}. "
             "Otros jugadores no podrán atacarte."
            if new_safe_mode
            else "Ahora puedes ser atacado por otros jugadores."
        )

        logger.info("SafeToggle user_id %d: %s", user_id, new_safe_mode)

        return CommandResult.ok(data={"user_id": user_id, "safe_mode": new_safe_mode})
