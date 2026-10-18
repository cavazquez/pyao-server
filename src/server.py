"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import redis.asyncio as redis

from src.config.config_manager import config_manager
from src.config.game_config import ServerConfig
from src.core.server_initializer import ServerInitializer
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.security.password_executor import close_password_executor
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
        endpoint = ServerConfig(
            host=host if host is not None else str(config_manager.get("server.host", "0.0.0.0")),
            port=port if port is not None else int(str(config_manager.get("server.port", 7666))),
        )
        self.host = endpoint.host
        self.port = endpoint.port
        self.max_connections = ServerConfig(
            max_connections=int(str(config_manager.get("server.max_connections", 1000)))
        ).max_connections
        self._active_connections = 0
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

        return self.task_factory.create_task(data, message_sender, session_data)  # type: ignore[arg-type]

    async def handle_client(  # noqa: PLR0915
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Maneja la conexión de un cliente.

        Args:
            reader: Stream para leer datos del cliente (pasado a ClientConnection).
            writer: Stream para escribir datos al cliente (pasado a ClientConnection).

        Raises:
            CancelledError: Al cancelar la tarea de conexión durante el apagado.
        """
        # No hay await entre comprobar y reservar: atómico dentro del event loop.
        if self._active_connections >= self.max_connections:
            logger.info("Conexión rechazada: límite de %d alcanzado", self.max_connections)
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                logger.debug("La conexión rechazada ya estaba cerrada")
            return
        self._active_connections += 1
        counted_in_redis = False
        session_data: dict[str, dict[str, int]] = {}
        try:
            connection = ClientConnection(reader, writer)
            message_sender = MessageSender(connection)
            logger.info("Nueva conexión desde %s", connection.address)
            if self.deps and self.deps.redis_client:
                await self.deps.redis_client.increment_connections()
                counted_in_redis = True
            while True:
                data = await connection.receive()
                if not data:
                    break
                task = self.create_task(data, message_sender, session_data)
                await task.execute()
        except asyncio.CancelledError:
            logger.debug("Conexión cancelada por shutdown")
            raise
        except Exception:
            logger.exception("Error manejando conexión")
        finally:
            try:
                await self._cleanup_player(session_data)
            except Exception:
                logger.exception("Error limpiando jugador desconectado")
            finally:
                # Incluso si falla el login, Redis o el cierre lógico, liberar exactamente una vez.
                self._active_connections -= 1
                try:
                    writer.close()
                    await writer.wait_closed()
                except ConnectionError:
                    logger.debug("El transporte ya estaba cerrado")
                finally:
                    if counted_in_redis and self.deps and self.deps.redis_client:
                        try:
                            await self.deps.redis_client.decrement_connections()
                        except Exception:
                            logger.exception("No se pudo actualizar la métrica de conexiones")

    async def _cleanup_player(self, session_data: dict[str, dict[str, int]]) -> None:
        """Retira el jugador del mundo al finalizar su conexión."""
        if "user_id" not in session_data or not self.deps or not self.deps.player_repo:
            return
        user_id_value = session_data["user_id"]
        if isinstance(user_id_value, dict):
            return
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

        # Limpiar mascotas del jugador
        if self.deps and self.deps.summon_service and self.deps.npc_service:
            try:
                pet_instance_ids = await self.deps.summon_service.remove_all_player_pets(user_id)
                # Remover cada mascota del mundo
                all_npcs = await self.deps.npc_service.npc_repository.get_all_npcs()
                for pet_instance_id in pet_instance_ids:
                    pet_npc = next(
                        (npc for npc in all_npcs if npc.instance_id == pet_instance_id),
                        None,
                    )
                    if pet_npc:
                        await self.deps.npc_service.remove_npc(pet_npc)
                        logger.info(
                            "Mascota removida al desconectar: user_id=%d, mascota=%s",
                            user_id,
                            pet_npc.name,
                        )
            except Exception:
                logger.exception("Error al limpiar mascotas del jugador %d al desconectar", user_id)

        # Remover jugador de todos los mapas
        self.deps.map_manager.remove_player_from_all_maps(user_id)

    async def start(self) -> None:
        """Inicia el servidor TCP."""
        try:
            # Inicializar todas las dependencias usando ServerInitializer
            self.deps, _, _ = await ServerInitializer.initialize_all()

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
            logger.error(  # noqa: TRY400
                "Podés iniciar Redis con:\n"
                "  snap:  sudo snap install redis && sudo snap start redis\n"
                "  deb:   sudo apt install redis-server && sudo systemctl start redis"
            )
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

        try:
            self.server = await asyncio.start_server(
                self.handle_client,
                self.host,
                self.port,
                ssl=ssl_context,
            )
        except OSError:
            logger.error(  # noqa: TRY400
                "No se pudo bindear al puerto %d en %s. Puerto ocupado.", self.port, self.host
            )
            logger.error("Cambiá el puerto con --port <número> o liberá el puerto %d.", self.port)  # noqa: TRY400
            sys.exit(1)

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

        await close_password_executor()

        # Desconectar de Redis
        if self.deps and self.deps.redis_client:
            await self.deps.redis_client.disconnect()
