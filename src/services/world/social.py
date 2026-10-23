"""Snapshots sociales autorizados para el personaje de la conexión vigente."""

from typing import TYPE_CHECKING, Any

from src.models.clan import ClanRank
from src.models.party import INVITATION_TIMEOUT_SECONDS

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

CLAN_PAGE_SIZE = 8


async def party_snapshot(deps: DependencyContainer, user: int) -> dict[str, Any]:
    """Consulta sólo el grupo y las invitaciones propias.

    Returns:
        Miembros, permisos y plazos con identidades estables.
    """
    party = await deps.party_service.get_party_info(user)
    invitations = sorted(
        await deps.party_service.get_user_invitations(user),
        key=lambda invitation: invitation.created_at,
        reverse=True,
    )[:8]
    data: dict[str, Any] = {
        "user": user,
        "party_id": 0,
        "leader": 0,
        "members": [],
        "invitations": [
            {
                "party_id": invitation.party_id,
                "from": invitation.inviter_username,
                "expires": int(invitation.created_at + INVITATION_TIMEOUT_SECONDS),
            }
            for invitation in invitations
            if not invitation.is_expired
        ],
        "permissions": [],
    }
    if not party or not party.is_member(user):
        data["permissions"] = ["create"]
        return data
    data.update(
        party_id=party.party_id,
        leader=party.leader_id,
        permissions=["leave"] + (["invite", "kick", "leader"] if party.is_leader(user) else []),
    )
    for member in sorted(party.members.values(), key=lambda member: member.user_id):
        stats = await deps.player_repo.get_stats(member.user_id) or {}
        position = await deps.player_repo.get_position(member.user_id) or {}
        data["members"].append(
            {
                "id": member.user_id,
                "name": member.username,
                "level": int(stats.get("level", member.level)),
                "online": deps.map_manager.get_player_message_sender(member.user_id) is not None,
                "map": position.get("map", 0),
                "hp": stats.get("min_hp", 0),
                "max_hp": stats.get("max_hp", 0),
            }
        )
    return data


async def clan_snapshot(deps: DependencyContainer, user: int, page: int) -> dict[str, Any]:
    """Pagina únicamente el clan del solicitante; no admite un clan_id externo.

    Returns:
        Página del roster con permisos calculados en servidor e invitación propia.

    Raises:
        ValueError: Si la página no existe.
    """
    clan = await deps.clan_repo.get_user_clan(user)
    invitation = await deps.clan_repo.get_invitation(user)
    data: dict[str, Any] = {
        "user": user,
        "clan_id": 0,
        "name": "",
        "leader": 0,
        "members": [],
        "permissions": ["create"],
        "page": 0,
        "pages": 1,
        "invitation": {},
    }
    if invitation and not invitation.is_expired():
        data["invitation"] = {
            "clan_id": invitation.clan_id,
            "name": invitation.clan_name,
            "from": invitation.inviter_username,
            "expires": int(invitation.expires_at),
        }
    actor = clan.get_member(user) if clan else None
    if clan is None or actor is None:
        return data
    permissions = [] if actor.rank == ClanRank.LEADER else ["leave"]
    if actor.can_invite_members():
        permissions.append("invite")
    if actor.can_manage_clan():
        permissions.append("transfer")
    if actor.rank == ClanRank.LEADER and clan.leader_id == user:
        permissions.append("profile")
    pages = max(1, (clan.member_count + CLAN_PAGE_SIZE - 1) // CLAN_PAGE_SIZE)
    if page < 0:
        message = "Página de clan fuera de rango"
        raise ValueError(message)
    page = min(page, pages - 1)
    data.update(
        clan_id=clan.clan_id,
        name=clan.name,
        leader=clan.leader_id,
        own_rank=int(actor.rank),
        permissions=permissions,
        page=page,
        pages=pages,
        member_count=clan.member_count,
        profile={
            "description": clan.description,
            "news": clan.news,
            "website": clan.website,
            "version": clan.profile_revision,
        },
    )
    for target in sorted(clan.members.values(), key=lambda member: member.user_id)[
        page * CLAN_PAGE_SIZE : (page + 1) * CLAN_PAGE_SIZE
    ]:
        actions = []
        if target.user_id != user and target.rank != ClanRank.LEADER:
            if actor.can_kick_members() and target.rank < actor.rank:
                actions.append("kick")
            if actor.can_promote_demote():
                if target.rank < ClanRank.VICE_LEADER:
                    actions.append("promote")
                if target.rank > ClanRank.MEMBER:
                    actions.append("demote")
            if actor.rank == ClanRank.LEADER:
                actions.append("transfer")
        data["members"].append(
            {
                "id": target.user_id,
                "name": target.username,
                "level": await deps.player_repo.get_level(target.user_id),
                "rank": int(target.rank),
                "online": deps.map_manager.get_player_message_sender(target.user_id) is not None,
                "actions": actions,
            }
        )
    return data
