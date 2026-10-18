"""Ejecutor Argon2 acotado compartido por el proceso."""

import asyncio
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from functools import lru_cache
from threading import Lock
from typing import Any

from src.config.config_manager import config_manager
from src.config.game_config import SecurityConfig


class PasswordQueueFullError(RuntimeError):
    """No hay capacidad para admitir otra operación de contraseña."""


class PasswordExecutor:
    """Limita trabajo activo y pendiente, conservando plazas tras cancelación."""

    def __init__(self, workers: int = 2, max_pending: int = 4) -> None:
        """Inicializa el pool sin arrancar hilos hasta el primer trabajo.

        Raises:
            ValueError: Si los límites no son válidos.
        """
        if workers < 1 or max_pending < 0:
            msg = "Límites de hashing inválidos"
            raise ValueError(msg)
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pyao-argon2")
        self._capacity = workers + max_pending
        self._jobs: set[Future[Any]] = set()
        self._lock = Lock()
        self._closed = False

    @property
    def outstanding(self) -> int:
        """Cantidad de trabajos admitidos que todavía ocupan una plaza."""
        with self._lock:
            return len(self._jobs)

    def _finished(self, future: Future[Any]) -> None:
        with self._lock:
            self._jobs.discard(future)

    async def run[T](self, operation: Callable[..., T], *args: object) -> T:
        """Ejecuta sin bloquear el loop ni admitir una cola ilimitada.

        La cancelación del solicitante no cancela el future nativo: una operación
        admitida conserva su plaza hasta terminar, incluso si aún estaba en cola.

        Returns:
            Resultado de la operación.

        Raises:
            PasswordQueueFullError: Si el pool está cerrado o saturado.
        """
        with self._lock:
            if self._closed or len(self._jobs) >= self._capacity:
                msg = "Servicio de autenticación ocupado; reintentá más tarde"
                raise PasswordQueueFullError(msg)
            future = self._executor.submit(operation, *args)
            self._jobs.add(future)
        future.add_done_callback(self._finished)
        wrapped = asyncio.wrap_future(future)
        # Si el solicitante se cancela, recoger igualmente errores sin logs de argumentos.
        wrapped.add_done_callback(lambda done: None if done.cancelled() else done.exception())
        return await asyncio.shield(wrapped)

    async def aclose(self) -> None:
        """Rechaza admisiones, cancela pendientes y espera los trabajos activos."""
        with self._lock:
            self._closed = True
            jobs = tuple(self._jobs)
        self._executor.shutdown(wait=False, cancel_futures=True)
        await asyncio.gather(*(asyncio.wrap_future(job) for job in jobs), return_exceptions=True)


@lru_cache(maxsize=1)
def get_password_executor() -> PasswordExecutor:
    """Obtiene el pool único usando los límites centrales validados.

    Returns:
        Ejecutor compartido por creación y verificación de contraseñas.
    """
    settings = SecurityConfig.model_validate(config_manager.get_section("security"))
    return PasswordExecutor(settings.hash_workers, settings.hash_max_pending)


async def close_password_executor() -> None:
    """Cierra el pool sólo si se utilizó; permite reiniciar en el mismo proceso."""
    if get_password_executor.cache_info().currsize:
        await get_password_executor().aclose()
        get_password_executor.cache_clear()
