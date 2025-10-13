"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import redis
from src.account_repository import AccountRepository
from src.client_connection import ClientConnection
from src.map_manager import MapManager
from src.message_sender import MessageSender
from src.packet_handlers import TASK_HANDLERS
from src.player_repository import PlayerRepository
from src.redis_client import RedisClient
from src.task_account import TaskCreateAccount
from src.task_attributes import TaskRequestAttributes
from src.task_change_heading import TaskChangeHeading
from src.task_dice import TaskDice
from src.task_login import TaskLogin
from src.task_null import TaskNull
from src.task_talk import TaskTalk
from src.task_walk import TaskWalk

if TYPE_CHECKING:
    from src.task import Task

logger = logging.getLogger(__name__)


class ArgentumServer:
    """Servidor TCP para Argentum Online."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 7666,
    ) -> None:
        """Inicializa el servidor.

        Args:
            host: Dirección IP donde escuchar (se sobrescribe con Redis).
            port: Puerto donde escuchar (se sobrescribe con Redis).
        """
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.redis_client: RedisClient | None = None
        self.player_repo: PlayerRepository | None = None
        self.account_repo: AccountRepository | None = None
        self.map_manager = MapManager()  # Gestor de jugadores por mapa

    def create_task(  # noqa: PLR0911
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]],
    ) -> Task:
        """Crea la tarea apropiada según el PacketID recibido.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            session_data: Datos de sesión (mutable, compartido entre tareas).

        Returns:
            Instancia de la tarea correspondiente.
        """
        if len(data) == 0:
            return TaskNull(data, message_sender)

        packet_id = data[0]

        # Buscar handler en el diccionario
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)

        # Pasar parámetros adicionales según el tipo de tarea
        if task_class is TaskLogin:
            return TaskLogin(
                data,
                message_sender,
                self.player_repo,
                self.account_repo,
                self.map_manager,
                session_data,
            )
        if task_class is TaskCreateAccount:
            return TaskCreateAccount(
                data,
                message_sender,
                self.player_repo,
                self.account_repo,
                self.map_manager,
                session_data,
            )
        if task_class is TaskDice:
            return TaskDice(data, message_sender, session_data)
        if task_class is TaskRequestAttributes:
            return TaskRequestAttributes(data, message_sender, self.player_repo, session_data)
        if task_class is TaskTalk:
            return TaskTalk(data, message_sender, session_data)
        if task_class is TaskWalk:
            return TaskWalk(data, message_sender, self.player_repo, self.map_manager, session_data)
        if task_class is TaskChangeHeading:
            return TaskChangeHeading(
                data, message_sender, self.player_repo, self.account_repo, session_data
            )

        return task_class(data, message_sender)

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Maneja la conexión de un cliente.

        Args:
            reader: Stream para leer datos del cliente (pasado a ClientConnection).
            writer: Stream para escribir datos al cliente (pasado a ClientConnection).
        """
        connection = ClientConnection(reader, writer)
        message_sender = MessageSender(connection)
        logger.info("Nueva conexión desde %s", connection.address)

        # Incrementar contador de conexiones en Redis
        if self.redis_client:
            await self.redis_client.increment_connections()
            connections = await self.redis_client.get_connections_count()
            logger.info("Conexiones activas: %d", connections)

        # Datos de sesión compartidos entre tareas (mutable)
        session_data: dict[str, dict[str, int]] = {}

        try:
            while True:
                data = await connection.receive()
                if not data:
                    break

                # Crear y ejecutar tarea apropiada según el mensaje
                task = self.create_task(data, message_sender, session_data)
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
        # Conectar a Redis (obligatorio)
        try:
            self.redis_client = RedisClient()
            await self.redis_client.connect()

            # Crear repositorios
            self.player_repo = PlayerRepository(self.redis_client)
            self.account_repo = AccountRepository(self.redis_client)

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
