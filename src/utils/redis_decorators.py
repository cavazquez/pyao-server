"""Decoradores para validación de Redis en repositorios."""

import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar, overload

logger = logging.getLogger(__name__)

P = ParamSpec("P")
T = TypeVar("T")


@overload
def require_redis(
    *,
    default_return: None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]: ...


@overload
def require_redis[T](
    *,
    default_return: T,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]: ...


def require_redis[T](
    *,
    default_return: T | None = None,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """Decorator que valida que Redis esté disponible antes de ejecutar el método.

    Args:
        default_return: Valor a retornar si Redis no está disponible.

    Returns:
        Decorator function.

    Example:
        ```python
        @require_redis(default_return=False)
        async def equip_item(self, user_id: int, slot: EquipmentSlot):
            # Ya no necesita validar self.redis is None
            ...
        ```
    """

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # El primer argumento debe ser self
            if not args:
                logger.error("@require_redis requiere al menos un argumento (self)")
                return default_return  # type: ignore[return-value]

            self = args[0]

            # Verificar si el objeto tiene atributo redis
            if not hasattr(self, "redis"):
                logger.error(
                    "Objeto %s no tiene atributo 'redis' para usar @require_redis",
                    self.__class__.__name__,
                )
                return default_return  # type: ignore[return-value]

            # Verificar si redis está disponible
            if self.redis is None:
                logger.error(
                    "Cliente Redis no disponible en %s.%s",
                    self.__class__.__name__,
                    func.__name__,
                )
                return default_return  # type: ignore[return-value]

            # Ejecutar función original
            return await func(*args, **kwargs)

        return wrapper

    return decorator
