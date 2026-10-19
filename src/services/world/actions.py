"""Adaptadores de acciones sociales que reutilizan permisos y reglas existentes."""

from typing import TYPE_CHECKING, Any

from src.services.expansion.service import EXPANSION_FIELDS, EXPANSION_TOPICS

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

ACTION_FIELDS: dict[str, dict[str, type]] = {
    "tax.read": {},
    "party.read": {},
    "clan.read": {"page": int},
    "pets.read": {},
    "weather.read": {},
    "commands.read": {},
    "subscribe": {"topic": str, "enabled": bool},
    "party.create": {},
    "party.invite": {"username": str},
    "party.accept": {"party_id": int},
    "party.reject": {"party_id": int},
    "party.leave": {},
    "party.kick": {"username": str},
    "party.leader": {"username": str},
    "clan.create": {"name": str, "description": str},
    "clan.invite": {"username": str},
    "clan.accept": {},
    "clan.reject": {},
    "clan.leave": {},
    "clan.kick": {"username": str},
    "clan.promote": {"username": str},
    "clan.demote": {"username": str},
    "clan.transfer": {"username": str},
    "pets.order": {"instance": str, "order": str},
    "pets.release": {"instance": str},
    "weather.set": {"map": int, "raining": bool, "intensity": int},
    "trade.read": {"session": str, "revision": int, "page": int},
}
TOPICS = frozenset({"tax", "party", "clan", "pets", "weather", "commands"})
ACTION_FIELDS.update(EXPANSION_FIELDS)
TOPICS |= EXPANSION_TOPICS


async def party_action(
    deps: DependencyContainer, user: int, action: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Resuelve el resultado desde el estado posterior, sin interpretar textos de chat.

    Returns:
        Mensaje del servicio y confirmación del cambio solicitado.
    """
    service = deps.party_service
    if action == "create":
        party, message = await service.create_party(
            user, deps.map_manager.get_player_username(user) or ""
        )
        return {"applied": party is not None, "message": message}
    if action == "reject":
        invitation = await deps.party_repo.get_invitation(user, params["party_id"])
        if invitation is None:
            return {"applied": False, "message": "La invitación ya no está disponible."}
        await deps.party_repo.remove_invitation(user, params["party_id"])
        return {"applied": True, "message": "Invitación rechazada."}
    before = await service.get_party_info(user)
    target = deps.map_manager.find_player_by_username(params.get("username", ""))
    if action == "accept":
        message = await service.accept_invitation(user, params["party_id"])
    elif action == "invite":
        message = await service.invite_to_party(user, params["username"])
    elif action == "leave":
        message = await service.leave_party(user)
    elif action == "kick":
        message = await service.kick_member(user, params["username"])
    else:
        message = await service.transfer_leadership(user, params["username"])
    after = await service.get_party_info(user)
    applied = False
    if action == "accept":
        applied = after is not None and after.party_id == params["party_id"]
    elif action == "leave":
        applied = before is not None and after is None
    elif action == "kick":
        applied = bool(
            before and after and target in before.member_ids and target not in after.member_ids
        )
    elif action == "leader":
        applied = bool(after and target == after.leader_id)
    elif action == "invite" and target and after:
        invitation = await deps.party_repo.get_invitation(target, after.party_id)
        applied = bool(invitation and invitation.inviter_id == user and not invitation.is_expired)
    return {"applied": applied, "message": message}


async def clan_action(
    deps: DependencyContainer, user: int, action: str, params: dict[str, Any]
) -> dict[str, Any]:
    """Conserva los controles de rango y distingue crear, ascender y transferir.

    Returns:
        Resultado confirmado por el servicio de clan.
    """
    service = deps.clan_service
    if action == "create":
        clan, message = await service.create_clan(user, params["name"], params["description"])
        return {"applied": clan is not None, "message": message}
    if action == "accept":
        clan, message = await service.accept_invitation(user)
        return {"applied": clan is not None, "message": message}
    if action == "invite":
        message = await service.invite_to_clan(user, params["username"])
        target = deps.map_manager.find_player_by_username(params["username"])
        invitation = await deps.clan_repo.get_invitation(target) if target else None
        return {"applied": bool(invitation and invitation.inviter_id == user), "message": message}
    if action == "reject":
        before = await deps.clan_repo.get_invitation(user)
        message = await service.reject_invitation(user)
        return {
            "applied": before is not None and await deps.clan_repo.get_invitation(user) is None,
            "message": message,
        }
    routes = {
        "kick": service.kick_member,
        "promote": service.promote_member,
        "demote": service.demote_member,
        "transfer": service.transfer_leadership,
    }
    if action == "leave":
        applied, message = await service.leave_clan(user)
    else:
        applied, message = await routes[action](user, params["username"])
    return {"applied": applied, "message": message}
