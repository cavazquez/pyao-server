"""Task para manejar intentos de handshake TLS cuando SSL está deshabilitado."""

import logging

from src.tasks.task import Task

logger = logging.getLogger(__name__)


class TaskTLSHandshake(Task):
    """Loguea y corta conexiones TLS cuando el servidor no soporta SSL."""

    async def execute(self) -> None:
        """Registra el intento de handshake TLS y cierra la conexión."""
        connection = self.message_sender.connection
        logger.warning(
            "Cliente %s intentó iniciar handshake TLS, pero el servidor no tiene SSL habilitado.",
            connection.address,
        )
        connection.close()
        await connection.wait_closed()
