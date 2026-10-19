"""Sintaxis soportada y permisos derivados del personaje, sin ejecutar texto."""

from typing import TYPE_CHECKING, Any

from src.models.clan import ClanRank

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

BASE_COMMANDS = (
    ("/ayuda", "/ayuda"),
    ("/est", "/est"),
    ("/meditar", "/meditar"),
    ("/boveda", "/boveda"),
    ("/depositar", "/depositar cantidad"),
    ("/retirar", "/retirar cantidad"),
    ("/balance", "/balance"),
    ("/comerciar", "/comerciar"),
    ("/descansar", "/descansar"),
    ("/contraseña", "/contraseña (abre formulario)"),
    ("/PET", "/PET INFO | LIBERAR | SEGUIR | ESPERAR"),
)


async def command_snapshot(deps: DependencyContainer, user: int) -> dict[str, Any]:
    """Expone sólo sintaxis real; las acciones siguen verificando sus propios permisos.

    Returns:
        Catálogo acotado según pertenencia, liderazgo y rangos vigentes.
    """
    commands = list(BASE_COMMANDS)
    party = await deps.party_service.get_party_info(user)
    if party is None:
        commands.extend(
            (
                ("/crearparty", "/crearparty"),
                ("/party", "/party nombre"),
                ("/acceptparty", "/acceptparty nombre"),
            )
        )
    else:
        commands.extend((("/salirparty", "/salirparty"), ("/pmsg", "/pmsg mensaje")))
        if party.is_leader(user):
            commands.extend(
                (
                    ("/party", "/party nombre"),
                    ("/echarparty", "/echarparty nombre"),
                    ("/partylider", "/partylider nombre"),
                )
            )
    clan = await deps.clan_repo.get_user_clan(user)
    actor = clan.get_member(user) if clan else None
    if actor is None:
        commands.append(("/CREARCLAN", "/CREARCLAN nombre [descripción]"))
        invitation = await deps.clan_repo.get_invitation(user)
        if invitation and not invitation.is_expired():
            commands.extend((("/ACEPTARCLAN", "/ACEPTARCLAN"), ("/RECHAZARCLAN", "/RECHAZARCLAN")))
    else:
        commands.extend((("/CLAN", "/CLAN mensaje"), ("/SALIRCLAN", "/SALIRCLAN")))
        if actor.can_invite_members():
            commands.extend(
                (("/INVITARCLAN", "/INVITARCLAN nombre"), ("/EXPULSARCLAN", "/EXPULSARCLAN nombre"))
            )
        if actor.can_promote_demote():
            commands.extend(
                (
                    ("/PROMOVERCLAN", "/PROMOVERCLAN nombre"),
                    ("/DEGRADARCLAN", "/DEGRADARCLAN nombre"),
                )
            )
        if actor.rank == ClanRank.LEADER:
            commands.append(("/TRANSFERIRLIDERAZGO", "/TRANSFERIRLIDERAZGO nombre"))
    return {"commands": [{"text": command, "syntax": syntax} for command, syntax in commands]}
