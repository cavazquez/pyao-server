"""Task para manejar intentos de handshake TLS cuando SSL está deshabilitado."""

import logging

from src.tasks.task import Task

logger = logging.getLogger(__name__)


class TaskTLSHandshake(Task):
    """Loguea y corta conexiones TLS cuando el servidor no soporta SSL."""

    async def execute(self) -> None:
        """Registra el intento de handshake TLS y cierra la conexión."""
        logger.warning(
            "Cliente %s intentó iniciar handshake TLS, pero el servidor no tiene SSL habilitado.",
            self.message_sender.address,
        )
        await self.message_sender.disconnect()
