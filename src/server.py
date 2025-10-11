"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys

import redis
from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.packet_handlers import TASK_HANDLERS
from src.redis_client import RedisClient
from src.task import Task, TaskCreateAccount, TaskNull

logger = logging.getLogger(__name__)


class ArgentumServer:
    """Servidor TCP para Argentum Online."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 7666,
        *,
        use_redis: bool = True,
    ) -> None:
        """Inicializa el servidor.

        Args:
            host: Dirección IP donde escuchar (se sobrescribe con Redis si está habilitado).
            port: Puerto donde escuchar (se sobrescribe con Redis si está habilitado).
            use_redis: Si True, usa Redis para configuración y estado.
        """
        self.host = host
        self.port = port
        self.use_redis = use_redis
        self.server: asyncio.Server | None = None
        self.redis_client: RedisClient | None = None

    def create_task(self, data: bytes, message_sender: MessageSender) -> Task:
        """Crea la tarea apropiada según el PacketID recibido.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.

        Returns:
            Instancia de la tarea correspondiente.
        """
        if len(data) == 0:
            return TaskNull(data, message_sender)

        packet_id = data[0]

        # Buscar handler en el diccionario
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)

        # Si es TaskCreateAccount, pasar redis_client
        if task_class is TaskCreateAccount:
            return TaskCreateAccount(data, message_sender, self.redis_client)

        return task_class(data, message_sender)

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
        message_sender = MessageSender(connection)
        logger.info("Nueva conexión desde %s", connection.address)

        # Incrementar contador de conexiones en Redis
        if self.redis_client:
            await self.redis_client.increment_connections()
            connections = await self.redis_client.get_connections_count()
            logger.info("Conexiones activas: %d", connections)

        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break

                logger.info("Recibidos %d bytes desde %s", len(data), connection.address)

                # Crear y ejecutar tarea apropiada según el mensaje
                task = self.create_task(data, message_sender)
                await task.execute()

        except Exception:
            logger.exception("Error manejando cliente %s", connection.address)
        finally:
            logger.info("Cerrando conexión con %s", connection.address)
            connection.close()
            await connection.wait_closed()

            # Decrementar contador de conexiones en Redis
            if self.redis_client:
                await self.redis_client.decrement_connections()
                connections = await self.redis_client.get_connections_count()
                logger.info("Conexiones activas: %d", connections)

    async def start(self) -> None:
        """Inicia el servidor TCP."""
        # Conectar a Redis si está habilitado
        if self.use_redis:
            try:
                self.redis_client = RedisClient()
                await self.redis_client.connect()

                # Obtener configuración desde Redis
                self.host = await self.redis_client.get_server_host()
                self.port = await self.redis_client.get_server_port()
                logger.info("Configuración cargada desde Redis: %s:%d", self.host, self.port)

                # Resetear contador de conexiones
                await self.redis_client.redis.set("server:connections:count", "0")

            except redis.ConnectionError as e:
                logger.error("No se pudo conectar a Redis: %s", e)  # noqa: TRY400
                logger.error(  # noqa: TRY400
                    "El servidor requiere Redis para funcionar. "
                    "Asegúrate de que Redis esté ejecutándose."
                )
                logger.error("Puedes iniciar Redis con: redis-server")  # noqa: TRY400
                sys.exit(1)
            except Exception:
                logger.exception("Error inesperado al conectar con Redis")
                sys.exit(1)

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

        # Desconectar de Redis
        if self.redis_client:
            await self.redis_client.disconnect()
