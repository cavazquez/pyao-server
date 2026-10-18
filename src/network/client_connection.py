"""Manejo de conexiones de cliente."""

import asyncio
import logging
from typing import TYPE_CHECKING

from src.security.auth_limits import AuthLimiter, ConnectionAttempts
from src.security.session_lease import SessionLease

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)


class ClientConnection:
    """Encapsula la conexión con un cliente y provee métodos para comunicación."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        max_outgoing_packets: int = 128,
        max_outgoing_bytes: int = 262144,
        drain_timeout: float = 5.0,
    ) -> None:
        """Inicializa la conexión del cliente.

        Args:
            reader: Stream para leer datos del cliente.
            writer: Stream para enviar datos al cliente.
            max_outgoing_packets: Límite de mensajes, incluido el que está en drain.
            max_outgoing_bytes: Límite de payload retenido, incluido el mensaje en vuelo.
            drain_timeout: Plazo máximo del escritor de esta conexión.

        Raises:
            ValueError: Si los límites de salida no son positivos.
        """
        if max_outgoing_packets < 1 or max_outgoing_bytes < 1 or drain_timeout <= 0:
            msg = "Límites de salida inválidos"
            raise ValueError(msg)
        self._outbox: asyncio.Queue[bytes] = asyncio.Queue(maxsize=max_outgoing_packets)
        self._max_outgoing_packets = max_outgoing_packets
        self._max_outgoing_bytes = max_outgoing_bytes
        self._drain_timeout = drain_timeout
        self._pending_packets = 0
        self._pending_bytes = 0
        self._writer_task: asyncio.Task[None] | None = None
        self._closed = False
        self._write_failed = False
        self.owner_task: asyncio.Task[object] | None = None
        self.auth_limiter: AuthLimiter | None = None
        self.auth_attempts = ConnectionAttempts()
        self.session_redis: Redis | None = None
        self.session_lease_seconds = 90
        self._session_lease: SessionLease | None = None
        self._lease_heartbeat: asyncio.Task[None] | None = None
        self.is_authenticated = False
        self.reader = reader
        self.writer = writer
        self.address = writer.get_extra_info("peername")
        self.is_ssl_enabled = writer.get_extra_info("ssl_object") is not None

    def allow_authentication(self, username: str) -> bool:
        """Consume el presupuesto de autenticación antes de ejecutar Argon2.

        Returns:
            True si el intento está permitido por conexión/IP/cuenta.
        """
        if self.is_authenticated:
            return False
        if self.auth_limiter is None:
            # Sólo conexiones de prueba/uso aislado carecen del limitador del servidor.
            return True
        ip = str(self.address[0]) if isinstance(self.address, tuple) else str(self.address)
        return self.auth_limiter.allow(ip, username, self.auth_attempts)

    async def reserve_session(self, user_id: int) -> bool:
        """Reserva una cuenta antes del spawn, manteniendo el propietario hasta cerrar.

        Returns:
            True si se adquirió la reserva.
        """
        if self._session_lease is not None:
            return False
        if self.session_redis is None:
            return True  # Conexiones de prueba sin persistencia.
        lease = SessionLease(self.session_redis, user_id, self.session_lease_seconds)
        self._session_lease = lease
        if not await lease.acquire():
            self._session_lease = None
            return False
        owner_task = asyncio.current_task()
        self._lease_heartbeat = asyncio.create_task(self._renew_session(lease, owner_task))
        return True

    async def _renew_session(
        self, lease: SessionLease, owner_task: asyncio.Task[object] | None
    ) -> None:
        try:
            while True:
                await asyncio.sleep(lease.ttl / 3)
                if not await lease.renew():
                    break
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception("No se pudo renovar la reserva de sesión")
        self.close()
        if owner_task is not None:
            owner_task.cancel()

    async def release_session(self) -> None:
        """Detiene la renovación y retira sólo la reserva de esta conexión."""
        if self._lease_heartbeat is not None:
            self._lease_heartbeat.cancel()
            await asyncio.gather(self._lease_heartbeat, return_exceptions=True)
            self._lease_heartbeat = None
        if self._session_lease is not None:
            lease, self._session_lease = self._session_lease, None
            await lease.release()

    @property
    def pending_packets(self) -> int:
        """Mensajes retenidos en cola o en el drain activo."""
        return self._pending_packets

    @property
    def pending_bytes(self) -> int:
        """Bytes de payload retenidos en cola o en el drain activo."""
        return self._pending_bytes

    async def send(self, data: bytes) -> None:
        """Encola sin esperar al drain de un cliente lento; preserva el orden.

        Al saturar se desconecta sólo este destinatario. Un broadcast puede
        continuar hacia los demás clientes sin propagar un fallo del peer cerrado.
        """
        if self._closed or not data:
            return
        if (
            self._pending_packets >= self._max_outgoing_packets
            or self._pending_bytes + len(data) > self._max_outgoing_bytes
        ):
            logger.warning("Cliente %s desconectado por saturación de salida", self.address)
            self._write_failed = True
            self.close(abort=True)
            return
        immutable = bytes(data)
        self._outbox.put_nowait(immutable)
        self._pending_packets += 1
        self._pending_bytes += len(immutable)
        if self._writer_task is None:
            self._writer_task = asyncio.create_task(self._write_loop(), name="pyao-client-writer")
        # Dar oportunidad al escritor evita saturar clientes rápidos en un burst de login.
        await asyncio.sleep(0)

    async def _write_loop(self) -> None:
        try:
            while True:
                data = await self._outbox.get()
                try:
                    self.writer.write(data)
                    async with asyncio.timeout(self._drain_timeout):
                        await self.writer.drain()
                    logger.debug("Enviados %d bytes a %s", len(data), self.address)
                finally:
                    self._pending_packets -= 1
                    self._pending_bytes -= len(data)
                    self._outbox.task_done()
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 - frontera de transporte, sin payload en log.
            # No imprimir argumentos de excepciones que puedan contener payloads.
            logger.warning("Escritor de %s cerrado: %s", self.address, type(error).__name__)
            self._write_failed = True
            self.close(abort=True)

    async def flush(self) -> None:
        """Espera la salida pendiente; usar antes de cerrar al drenar el servidor.

        Raises:
            ConnectionError: Si la cola se descartó por cierre/error del transporte.
        """
        await self._outbox.join()
        if self._write_failed:
            msg = "La conexión se cerró con salida pendiente"
            raise ConnectionError(msg)

    async def receive(self, max_bytes: int = 1024) -> bytes:
        """Recibe datos del cliente.

        Args:
            max_bytes: Número máximo de bytes a leer.

        Returns:
            Bytes recibidos del cliente (vacío si la conexión se cerró).
        """
        data = await self.reader.read(max_bytes)
        if data:
            logger.debug("Recibidos %d bytes de %s", len(data), self.address)
        return data

    def close(self, *, abort: bool = False) -> None:
        """Cierra y descarta salida pendiente, cancelando sólo el escritor propio."""
        if self._closed:
            return
        self._closed = True
        self._write_failed = self._write_failed or self._pending_packets > 0
        while not self._outbox.empty():
            data = self._outbox.get_nowait()
            self._pending_packets -= 1
            self._pending_bytes -= len(data)
            self._outbox.task_done()
        if (
            self._writer_task is not None
            and not self._writer_task.done()
            and self._writer_task is not asyncio.current_task()
        ):
            self._writer_task.cancel()
        if abort:
            self.writer.transport.abort()
            if self.owner_task is not None:
                self.owner_task.cancel()
        self.writer.close()

    async def wait_closed(self) -> None:
        """Espera también el escritor para no dejar tareas o buffers huérfanos."""
        if self._writer_task is not None:
            await asyncio.gather(self._writer_task, return_exceptions=True)
        await self.writer.wait_closed()
