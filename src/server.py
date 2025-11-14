"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import redis
from src.config.config_manager import config_manager
from src.core.server_initializer import ServerInitializer
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.security.ssl_manager import SSLConfigurationError, SSLManager
from src.tasks.task_factory import TaskFactory
from src.tasks.task_null import TaskNull

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.tasks.task import Task

logger = logging.getLogger(__name__)


class ArgentumServer:
    """Servidor TCP para Argentum Online."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        ssl_manager: SSLManager | None = None,
    ) -> None:
        """Inicializa el servidor.

        Args:
            host: Dirección IP donde escuchar (usa config si es None).
            port: Puerto donde escuchar (usa config si es None).
            ssl_manager: Gestor de configuración SSL.
        """
        self.host = host or config_manager.get("server.host", "0.0.0.0")
        self.port = port or config_manager.get("server.port", 7666)
        self.ssl_manager = ssl_manager or SSLManager.disabled()
        self.server: asyncio.Server | None = None
        self.deps: DependencyContainer | None = None  # Contenedor de dependencias
        self.task_factory: TaskFactory | None = None  # Factory para crear tasks

    def create_task(
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
        if not self.task_factory:
            # Fallback si el factory no está inicializado
            return TaskNull(data, message_sender)

        return self.task_factory.create_task(data, message_sender, session_data)

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
        if self.deps and self.deps.redis_client:
            await self.deps.redis_client.increment_connections()
            connections = await self.deps.redis_client.get_connections_count()
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

        except (KeyboardInterrupt, asyncio.CancelledError):
            # Shutdown graceful, no loguear como error
            logger.debug("Cliente %s desconectado por shutdown del servidor", connection.address)
        except Exception:
            logger.exception("Error manejando cliente %s", connection.address)
        finally:
            logger.info("Cerrando conexión con %s", connection.address)

            # Broadcast multijugador: notificar desconexión
            if "user_id" in session_data and self.deps and self.deps.player_repo:
                user_id_value = session_data["user_id"]
                if not isinstance(user_id_value, dict):
                    user_id = int(user_id_value)

                    # Obtener el mapa del jugador antes de removerlo
                    position = await self.deps.player_repo.get_position(user_id)
                    if position:
                        map_id = position["map"]

                        # Enviar CHARACTER_REMOVE a todos los jugadores en el mapa
                        other_senders = self.deps.map_manager.get_all_message_senders_in_map(
                            map_id, exclude_user_id=user_id
                        )
                        for sender in other_senders:
                            await sender.send_character_remove(user_id)

                        logger.info(
                            "Desconexión de user %d notificada a %d jugadores en mapa %d",
                            user_id,
                            len(other_senders),
                            map_id,
                        )

                    # Remover jugador de todos los mapas
                    self.deps.map_manager.remove_player_from_all_maps(user_id)

            connection.close()
            await connection.wait_closed()

            # Decrementar contador de conexiones en Redis
            if self.deps and self.deps.redis_client:
                await self.deps.redis_client.decrement_connections()
                connections = await self.deps.redis_client.get_connections_count()
                logger.info("Conexiones activas: %d", connections)

    async def start(self) -> None:
        """Inicia el servidor TCP."""
        try:
            # Inicializar todas las dependencias usando ServerInitializer
            self.deps, self.host, self.port = await ServerInitializer.initialize_all()

            # Crear TaskFactory con las dependencias
            self.task_factory = TaskFactory(self.deps)
            logger.info("✓ TaskFactory inicializado")

            # Iniciar el sistema de tick
            self.deps.game_tick.start()
            logger.info("✓ Sistema de tick del juego iniciado")

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

        try:
            ssl_context = self.ssl_manager.build_context()
            if ssl_context:
                logger.info("✓ Contexto SSL inicializado correctamente")
        except SSLConfigurationError:
            logger.exception("Error inicializando el contexto SSL")
            sys.exit(1)

        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
            ssl=ssl_context,
        )

        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info("Servidor escuchando en %s", addrs)

        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Detiene el servidor."""
        # Detener sistema de tick del juego
        if self.deps and self.deps.game_tick:
            await self.deps.game_tick.stop()
            logger.info("Sistema de tick del juego detenido")

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Servidor detenido")

        # Desconectar de Redis
        if self.deps and self.deps.redis_client:
            await self.deps.redis_client.disconnect()
