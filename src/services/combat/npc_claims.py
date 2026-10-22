"""Propiedad temporal de criaturas y permiso clásico /COMPARTIRNPC."""

from typing import TYPE_CHECKING, cast

from src.services.classic_chat.world_rules import rules

if TYPE_CHECKING:
    from src.utils.resource_transaction import Snapshot

CLAIM_SECONDS = 20


def sharing_key(user: int) -> str:
    """Identifica los dueños que compartieron sus criaturas con el atacante.

    Returns:
        Conjunto persistente y acotado de permisos concedidos al jugador.
    """
    return f"npc:shared_with:{user}"


def claim_rejection(snapshot: Snapshot, npc: dict[str, str], user: int, now: float) -> str:
    """Impide robar una criatura reclamada, salvo permiso explícito de su dueño.

    Returns:
        Mensaje de rechazo o cadena vacía.
    """
    owner = int(npc.get("combat_owner", 0))
    if rules(snapshot, int(npc.get("map_id", 0))).get("allow_npc_steal") == "1":
        return ""
    shared = cast("set[str]", snapshot.get(sharing_key(user)) or set())
    if (
        owner not in {0, user}
        and float(npc.get("claim_until", 0)) > now
        and str(owner) not in shared
    ):
        return "Esa criatura pertenece al combate de otro jugador; debe compartirla contigo."
    return ""


def claim_changes(npc: dict[str, str], user: int, now: float) -> dict[str, str]:
    """Conserva al dueño al compartir y renueva la reserva sólo por un ataque real.

    Returns:
        Campos del mismo commit que aplica el daño.
    """
    owner = int(npc.get("combat_owner", 0))
    if not owner or float(npc.get("claim_until", 0)) <= now:
        owner = user
    return {"combat_owner": str(owner), "claim_until": str(now + CLAIM_SECONDS)}
