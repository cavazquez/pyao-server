"""Servidor TCP para Argentum Online."""

import asyncio
import logging

from src.client_connection import ClientConnection
from src.packet_handlers import TASK_HANDLERS
from src.task import Task, TaskNull

logger = logging.getLogger(__name__)


class ArgentumServer:
    """Servidor TCP para Argentum Online."""

    def __init__(self, host: str = "0.0.0.0", port: int = 7666) -> None:
        """Inicializa el servidor.

        Args:
            host: Dirección IP donde escuchar.
            port: Puerto donde escuchar.
        """
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None

    @staticmethod
    def create_task(data: bytes, connection: ClientConnection) -> Task:
        """Crea la tarea apropiada según el PacketID recibido.

        Args:
            data: Datos recibidos del cliente.
            connection: Conexión con el cliente.

        Returns:
            Instancia de la tarea correspondiente.
        """
        if len(data) == 0:
            return TaskNull(data, connection)

        packet_id = data[0]

        # Buscar handler en el diccionario
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)
        return task_class(data, connection)

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Maneja la conexión de un cliente.

        Args:
            reader: Stream para leer datos del cliente.
            writer: Stream para escribir datos al cliente.
        """
        connection = ClientConnection(writer)
        logger.info("Nueva conexión desde %s", connection.address)

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                logger.info("Recibidos %d bytes desde %s", len(data), connection.address)

                # Crear y ejecutar tarea apropiada según el mensaje
                task = self.create_task(data, connection)
                await task.execute()

        except Exception:
            logger.exception("Error manejando cliente %s", connection.address)
        finally:
            logger.info("Cerrando conexión con %s", connection.address)
            connection.close()
            await connection.wait_closed()

    async def start(self) -> None:
        """Inicia el servidor TCP."""
        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )

        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info("Servidor escuchando en %s", addrs)

        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Detiene el servidor."""
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Servidor detenido")
