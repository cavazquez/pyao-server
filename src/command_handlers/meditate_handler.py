"""Handler para comando de meditación."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.meditate_command import MeditateCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class MeditateCommandHandler(CommandHandler):
    """Handler para comando de meditación (solo lógica de negocio)."""

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
        """Ejecuta el comando de toggle de meditación (solo lógica de negocio).

        Args:
            command: Comando de meditación.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, MeditateCommand):
            return CommandResult.error("Comando inválido: se esperaba MeditateCommand")

        user_id = command.user_id

        logger.info("MeditateCommandHandler: toggle de meditación para user_id %d", user_id)

        try:
            # Obtener estado actual de meditación
            is_currently_meditating = await self.player_repo.is_meditating(user_id)

            # Toggle: cambiar estado
            new_state = not is_currently_meditating
            await self.player_repo.set_meditating(user_id, new_state)

            # Enviar toggle de meditación al cliente
            await self.message_sender.send_meditate_toggle()

            # Mensaje al jugador y efectos visuales
            if new_state:
                await self.message_sender.send_console_msg(
                    "Comienzas a meditar. Recuperaras mana automaticamente."
                )
                # Enviar FX de meditación con loop infinito (loops=-1)
                # FX 16 es el efecto de meditación en Argentum Online
                # Para jugadores, char_index = user_id (NPCs usan char_index >= 10001)
                await self.message_sender.send_create_fx(
                    char_index=user_id,
                    fx=16,
                    loops=-1,  # loops=-1 = infinito
                )
                logger.info("user_id %d comenzó a meditar", user_id)
            else:
                await self.message_sender.send_console_msg("Dejas de meditar.")
                # Cancelar FX de meditación enviando el mismo FX con loops=0
                # Esto detiene el efecto visual inmediatamente
                await self.message_sender.send_create_fx(
                    char_index=user_id,
                    fx=16,
                    loops=0,  # loops=0 = cancela el FX
                )
                logger.info("user_id %d dejó de meditar", user_id)

            return CommandResult.ok(
                data={
                    "user_id": user_id,
                    "is_meditating": new_state,
                }
            )

        except Exception:
            logger.exception("Error al procesar toggle de meditación")
            return CommandResult.error("Error interno al procesar meditación")
