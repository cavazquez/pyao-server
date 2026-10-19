"""Catálogo de ofertas paginado, vinculado a la sesión y revisión del intercambio."""

import math
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

ITEMS_PER_PAGE = 3


def trade_metadata(
    deps: DependencyContainer, user: int, session_id: str, revision: int, page: int
) -> dict[str, Any]:
    """No acepta ofertas ni propiedades enviadas por el cliente como catálogo.

    Returns:
        Metadatos actuales de artículos efectivamente ofrecidos por los dos participantes.

    Raises:
        ValueError: Si la conexión o revisión ya no pertenece al intercambio.
    """
    session = deps.trade_service.get_session(user)
    sender = deps.map_manager.get_player_message_sender(user)
    if (
        session is None
        or session.session_id != session_id
        or session.revision != revision
        or session.senders.get(user) is not sender
    ):
        message = "El intercambio cambió; espera su estado actualizado."
        raise ValueError(message)
    identities = sorted(
        {
            item.item_id
            for offer in (session.initiator_offer, session.target_offer)
            for item in offer.items.values()
        }
    )
    pages = max(1, math.ceil(len(identities) / ITEMS_PER_PAGE))
    if not 0 <= page < pages:
        message = "Página de objetos inválida"
        raise ValueError(message)
    items = []
    for item_id in identities[page * ITEMS_PER_PAGE : (page + 1) * ITEMS_PER_PAGE]:
        item = deps.item_catalog.get_item_data(item_id)
        if item is None:
            items.append({"id": item_id, "known": False, "name": f"Objeto #{item_id}"})
            continue
        items.append(
            {
                "id": item_id,
                "known": True,
                "name": (deps.item_catalog.get_item_name(item_id) or f"Objeto #{item_id}")[:80],
                "graphic": int(str(item.get("GrhIndex", 0))),
                "type": int(str(item.get("ObjType", 0))),
                "min_hit": int(str(item.get("MinHIT", 0))),
                "max_hit": int(str(item.get("MaxHIT", 0))),
                "min_def": int(str(item.get("MinDef", 0))),
                "max_def": int(str(item.get("MaxDef", 0))),
                "value": int(str(item.get("Valor", 0))),
            }
        )
    return {
        "session": session_id,
        "trade_revision": revision,
        "page": page,
        "pages": pages,
        "items": items,
    }
