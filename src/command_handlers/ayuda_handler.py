"""Handler para comando de ayuda."""

import logging
from typing import TYPE_CHECKING

from src.commands.ayuda_command import AyudaCommand
from src.commands.base import Command, CommandHandler, CommandResult

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class AyudaCommandHandler(CommandHandler):
    """Handler para comando de ayuda (solo lógica de negocio)."""

    def __init__(
        self,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            message_sender: Enviador de mensajes.
        """
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de ayuda (solo lógica de negocio).

        Args:
            command: Comando de ayuda.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, AyudaCommand):
            return CommandResult.error("Comando inválido: se esperaba AyudaCommand")

        logger.debug(
            "AyudaCommandHandler: solicitud de ayuda desde %s",
            self.message_sender.connection.address,
        )

        try:
            # Mensaje de ayuda con comandos disponibles
            help_message = (
                "--- Comandos Disponibles ---\n"
                "/AYUDA - Muestra esta ayuda\n"
                "/EST - Muestra tus estadisticas\n"
                "/ONLINE - Lista de jugadores conectados\n"
                "/MOTD - Mensaje del dia del servidor\n"
                "/UPTIME - Tiempo de actividad del servidor\n"
                "/INFO - Informacion del servidor\n"
                "/METRICS - Metricas de rendimiento del servidor\n"
                "/SALIR - Desconectarse del servidor\n"
                "--- Comandos de Party ---\n"
                "/CREARPARTY - Crear una nueva party (nivel 15+)\n"
                "/PARTY <nombre> - Invitar jugador a tu party\n"
                "/ACCEPTPARTY <lider> - Aceptar invitacion de party\n"
                "/SALIRPARTY - Abandonar la party actual\n"
                "/PMSG <mensaje> - Enviar mensaje a tu party\n"
                "/KICK <nombre> - Expulsar miembro (solo lider)\n"
                "/PARTYLIDER <nombre> - Transferir liderazgo (solo lider)\n"
                "--- Informacion ---\n"
                "Usa las teclas de direccion para moverte\n"
                "Escribe en el chat para hablar con otros jugadores"
            )

            # Enviar ayuda línea por línea
            await self.message_sender.send_multiline_console_msg(help_message)
            logger.debug("Ayuda enviada a %s", self.message_sender.connection.address)

            return CommandResult.ok(data={"help_message": help_message})

        except Exception:
            logger.exception("Error al procesar solicitud de ayuda")
            return CommandResult.error("Error interno al procesar ayuda")
