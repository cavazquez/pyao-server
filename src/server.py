"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys
from collections.abc import Awaitable
from typing import TYPE_CHECKING
from uuid import uuid4

import redis.asyncio as redis

from src.config.config_manager import config_manager
from src.config.game_config import SecurityConfig, ServerConfig
from src.core.server_initializer import ServerInitializer
from src.log_context import connection_id, operation
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_framer import FramingError, PacketFramer
from src.security.auth_limits import AuthLimiter
from src.security.password_executor import close_password_executor
from src.security.ssl_manager import SSLConfigurationError, SSLManager
from src.tasks.task_factory import TaskFactory
from src.tasks.task_null import TaskNull

if TYPE_CHECKING:
    from websockets.asyncio.server import Server as WebSocketServer

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
        self.outgoing_config = ServerConfig.model_validate(config_manager.get_section("server"))
        self.host = endpoint.host
        self.port = endpoint.port
        self.max_connections = ServerConfig(
            max_connections=int(str(config_manager.get("server.max_connections", 1000)))
        ).max_connections
        security = SecurityConfig.model_validate(config_manager.get_section("security"))
        self.auth_timeout_seconds = security.auth_timeout_seconds
        self.session_lease_seconds = security.session_lease_seconds
        self.auth_limiter = AuthLimiter(security)
        self._active_connections = 0
        self._stopping = False
        self._stop_task: asyncio.Task[None] | None = None
        self._client_tasks: set[asyncio.Task[None]] = set()
        self._receivers: set[asyncio.Task[bytes]] = set()
        self._connections: set[ClientConnection] = set()
        self.ssl_manager = ssl_manager or SSLManager.disabled()
        self.server: asyncio.Server | None = None
        self.websocket_server: WebSocketServer | None = None
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

    async def handle_client(  # ruff: ignore[too-many-statements]
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
        if self._stopping or self._active_connections >= self.max_connections:
            logger.info("Conexión rechazada: límite de %d alcanzado", self.max_connections)
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                logger.debug("La conexión rechazada ya estaba cerrada")
            return
        self._active_connections += 1
        owner = asyncio.current_task()
        if owner is not None:
            self._client_tasks.add(owner)
        context_token = connection_id.set(uuid4().hex)
        counted_in_redis = False
        session_data: dict[str, dict[str, int]] = {}
        connection: ClientConnection | None = None
        message_sender: MessageSender | None = None
        try:
            connection = ClientConnection(
                reader,
                writer,
                max_outgoing_packets=self.outgoing_config.outgoing_max_packets,
                max_outgoing_bytes=self.outgoing_config.outgoing_max_bytes,
                drain_timeout=self.outgoing_config.outgoing_drain_timeout,
            )
            connection.owner_task = asyncio.current_task()
            self._connections.add(connection)
            connection.auth_limiter = self.auth_limiter
            connection.session_lease_seconds = self.session_lease_seconds
            if self.deps and self.deps.redis_client:
                connection.session_redis = self.deps.redis_client.redis
            deadline = asyncio.get_running_loop().time() + self.auth_timeout_seconds
            message_sender = MessageSender(connection)
            logger.info("Nueva conexión desde %s", connection.address)
            if self.deps and self.deps.redis_client:
                await self.deps.redis_client.increment_connections()
                counted_in_redis = True
            framer = PacketFramer()
            while not self._stopping:
                async with asyncio.timeout_at(None if connection.is_authenticated else deadline):
                    data = await self._receive(connection)
                    if not data:
                        if framer.buffer_size:
                            logger.info(
                                "EOF con paquete incompleto: %d bytes pendientes",
                                framer.buffer_size,
                            )
                        break
                    framer.feed(data)
                    while (packet := framer.next_packet()) is not None:
                        if self._stopping:
                            break
                        task = self.create_task(packet, message_sender, session_data)
                        with operation(uuid4().hex):
                            await task.execute()
        except FramingError as error:
            logger.info("Conexión cerrada por framing inválido: %s", error)
        except TimeoutError:
            logger.info("Conexión cerrada por plazo de autenticación agotado")
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError) as error:
            logger.info("Conexión terminada por el cliente: %s", type(error).__name__)
        except asyncio.CancelledError:
            logger.debug("Conexión cancelada por shutdown")
            raise
        except Exception:
            logger.exception("Error manejando conexión")
        finally:
            if connection is not None:
                # Un escritor que detecta RST ya no debe cancelar la limpieza de su dueño.
                connection.owner_task = None
            try:
                try:
                    await self._cleanup_player(session_data, message_sender)
                except Exception:
                    logger.exception("Error limpiando jugador desconectado")
                finally:
                    if connection is not None:
                        await self._release_connection(connection)
            finally:
                self._active_connections -= 1
                try:
                    await self._close_transport(connection, writer, counted_in_redis)
                finally:
                    if connection is not None:
                        self._connections.discard(connection)
                    if owner is not None:
                        self._client_tasks.discard(owner)
                    connection_id.reset(context_token)

    async def _release_connection(self, connection: ClientConnection) -> None:
        """Libera la reserva incluso si se canceló la limpieza del personaje."""
        try:
            await connection.release_session()
        except Exception:
            logger.exception("No se pudo liberar la reserva; vencerá por TTL")
        if self._stopping:
            try:
                await connection.flush()
            except ConnectionError:
                logger.debug("La salida de la sesión ya estaba cerrada")

    async def _close_transport(
        self, connection: ClientConnection | None, writer: asyncio.StreamWriter, counted: bool
    ) -> None:
        """Cierra siempre el socket y ajusta métricas antes de retirar al dueño."""
        try:
            if connection is not None:
                connection.close()
                await connection.wait_closed()
            else:
                writer.close()
                await writer.wait_closed()
        except ConnectionError:
            logger.debug("El transporte ya estaba cerrado")
        finally:
            try:
                if counted and self.deps and self.deps.redis_client:
                    await self.deps.redis_client.decrement_connections()
            except Exception:
                logger.exception("No se pudo actualizar la métrica de conexiones")

    async def _receive(self, connection: ClientConnection) -> bytes:
        """Permite despertar lectores ociosos sin cancelar una operación en curso.

        Returns:
            Bytes de red o EOF lógico cuando comienza el cierre.

        Raises:
            CancelledError: Si se cancela el handler, en lugar de sólo su lectura.
        """
        reader = asyncio.create_task(connection.receive(), name="pyao-client-reader")
        self._receivers.add(reader)
        if self._stopping:
            reader.cancel()
        try:
            return await reader
        except asyncio.CancelledError:
            owner = asyncio.current_task()
            if self._stopping and owner is not None and not owner.cancelling():
                return b""
            raise
        finally:
            self._receivers.discard(reader)

    async def _cleanup_player(
        self, session_data: dict[str, dict[str, int]], message_sender: MessageSender | None = None
    ) -> None:
        """Retira el jugador del mundo al finalizar su conexión."""
        if "user_id" not in session_data or not self.deps or not self.deps.player_repo:
            return
        user_id_value = session_data["user_id"]
        if isinstance(user_id_value, dict):
            return
        user_id = int(user_id_value)
        if message_sender is not None:
            current = self.deps.map_manager.get_player_message_sender(user_id)
            if current is not message_sender:
                return
        if self.deps.trade_service:
            await self.deps.trade_service.cancel_trade(user_id, "Un participante se desconectó.")
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
            from src.economy.maintenance import EconomyMaintenance  # ruff: ignore[import-outside-top-level]

            deps = self.deps

            async def devalue_ground(_redis: object, map_id: int) -> None:
                await deps.map_manager.settle_ground_devaluation(map_id, deps.broadcast_service)

            self._economy = EconomyMaintenance(self.deps.redis_client.redis, devalue_ground)
            self._economy.start()
            if self.deps.world_state:
                self.deps.world_state.start()
            logger.info("✓ Sistema de tick del juego iniciado")

        except redis.ConnectionError as e:
            logger.error("No se pudo conectar a Redis: %s", e)  # ruff: ignore[error-instead-of-exception]
            logger.error(  # ruff: ignore[error-instead-of-exception]
                "El servidor requiere Redis para funcionar. "
                "Asegúrate de que Redis esté ejecutándose."
            )
            logger.error(  # ruff: ignore[error-instead-of-exception]
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
                ssl_handshake_timeout=self.auth_timeout_seconds if ssl_context else None,
            )
        except OSError:
            logger.error(  # ruff: ignore[error-instead-of-exception]
                "No se pudo bindear al puerto %d en %s. Puerto ocupado.", self.port, self.host
            )
            logger.error("Cambiá el puerto con --port <número> o liberá el puerto %d.", self.port)  # ruff: ignore[error-instead-of-exception]
            sys.exit(1)

        if self.outgoing_config.wss_port:
            from src.network.websocket_transport import start_websocket  # ruff: ignore[import-outside-top-level] - transporte optativo.

            self.websocket_server = await start_websocket(
                self.handle_client,
                self.outgoing_config.wss_host,
                self.outgoing_config.wss_port,
                self.outgoing_config.wss_origins,
                ssl_context,
                tls_proxy=self.outgoing_config.wss_tls_proxy,
            )
        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info("Servidor escuchando en %s", addrs)

        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Cierra una sola vez; un solicitante cancelado no cancela el cierre compartido."""
        if self._stop_task is None:
            self._stopping = True
            if self.server:
                self.server.close()
            if self.websocket_server:
                self.websocket_server.close()
            for reader in tuple(self._receivers):
                reader.cancel()
            self._stop_task = asyncio.create_task(self._shutdown(), name="pyao-shutdown")
        await asyncio.shield(self._stop_task)

    @staticmethod
    async def _shutdown_step(operation: Awaitable[object], label: str, deadline: float) -> None:
        """Acota cada paso al presupuesto restante sin omitir los pasos posteriores."""
        try:
            async with asyncio.timeout_at(max(deadline, asyncio.get_running_loop().time() + 0.001)):
                await operation
        except TimeoutError:
            logger.warning("Plazo de cierre agotado en %s", label)
        except Exception:
            logger.exception("Fallo cerrando %s", label)

    async def _shutdown(self) -> None:
        """Drena handlers y trabajos propios antes de cerrar las conexiones Redis."""
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.outgoing_config.shutdown_timeout_seconds
        work_deadline = deadline - 1
        if self.websocket_server:
            await self._shutdown_step(self.websocket_server.wait_closed(), "WSS", work_deadline)
        if self.deps and self.deps.world_state:
            await self._shutdown_step(
                self.deps.world_state.close(), "estado de interfaz", work_deadline
            )
        economy = getattr(self, "_economy", None)
        if economy is not None:
            await self._shutdown_step(economy.close(), "economía", work_deadline)
        if self.deps and self.deps.game_tick:
            await self._shutdown_step(self.deps.game_tick.stop(), "tick", work_deadline)
        tasks = tuple(self._client_tasks)
        if tasks:
            _, pending = await asyncio.wait(
                tasks,
                timeout=max(
                    0, min(self.outgoing_config.shutdown_drain_seconds, work_deadline - loop.time())
                ),
            )
            for task in pending:
                task.cancel()
            await self._shutdown_step(
                asyncio.gather(*tasks, return_exceptions=True), "sesiones", work_deadline
            )
        # El cierre forzado conserva recibos/journals; no compensa commits inciertos.
        for connection in tuple(self._connections):
            connection.close(abort=True)
        if self.deps and self.deps.trade_service:
            await self._shutdown_step(self.deps.trade_service.close(), "trades", work_deadline)
        if self.deps and self.deps.player_death_service:
            await self._shutdown_step(
                self.deps.player_death_service.close(
                    deadline_seconds=max(0, work_deadline - loop.time())
                ),
                "ciclo de vida",
                work_deadline,
            )
        await self._shutdown_step(close_password_executor(), "autenticación", work_deadline)
        if self.server:
            # Incluye sockets cuyo handshake TLS aún no llegó a handle_client.
            self.server.abort_clients()
            await self._shutdown_step(self.server.wait_closed(), "listener", work_deadline)
        if self.deps and self.deps.redis_client:
            await self._shutdown_step(self.deps.redis_client.disconnect(), "Redis", deadline)
        logger.info("Servidor detenido; sesiones activas: %d", self._active_connections)
