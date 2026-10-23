"""Índice derivado de mascotas; la instancia Redis sigue siendo la autoridad."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.asyncio.client import Pipeline


def owner_key(user_id: int) -> str:
    """Devuelve el índice acotado a un propietario.

    Returns:
        Clave Redis del conjunto de instancias.
    """
    return f"player:{user_id}:pets"


def pet_owner(data: Mapping[str, str]) -> int:
    """Excluye muertos y seguidores administrativos, sin descartar invocaciones vencidas.

    Returns:
        Dueño o cero. La expiración se valida al leer y se elimina por el efecto.
    """
    user = int(data.get("summoned_by_user_id", 0))
    return (
        user
        if user > 0
        and int(data.get("hp", 0)) > 0
        and (
            data.get("is_tamed", "False").lower() == "true"
            or float(data.get("summoned_until", 0)) > 0
        )
        else 0
    )


def enqueue_pet_index(
    pipe: Pipeline, instance: str, before: Mapping[str, str], after: Mapping[str, str]
) -> None:
    """Actualiza sólo membresías derivadas, dentro del mismo EXEC que la instancia."""
    previous, current = pet_owner(before), pet_owner(after)
    if previous and previous != current:
        pipe.srem(owner_key(previous), instance)
    if current and current != previous:
        pipe.sadd(owner_key(current), instance)
