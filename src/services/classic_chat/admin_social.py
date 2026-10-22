"""Administración de facciones, consejos y clanes sin suplantar al líder."""

import json
from dataclasses import asdict
from typing import TYPE_CHECKING, cast

from src.models.clan import MAX_CLAN_NAME_LENGTH, Clan
from src.services.classic_chat.admin_common import audited
from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

FIRST_PRINTABLE_CHARACTER = 32

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable


async def faction_admin(ctx: ChatContext) -> None:
    """Gestiona consejos, expulsión permanente y reinicio del progreso de facción."""
    target = await ctx.account(ctx.arguments)
    user = int(target["user_id"])
    key = RedisKeys.player_user_stats(user)
    alignment = "royal" if ctx.command in {"/ACEPTCONSE", "/NOREAL"} else "chaos"

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[key])
        if ctx.command in {"/ACEPTCONSE", "/ACEPTCONSECAOS"}:
            if before.get("faction_id") != alignment:
                return Decision(
                    {"applied": False, "message": "El jugador no pertenece a esa facción."}, {}
                )
            changes = {"faction_council": "1"}
        elif ctx.command == "/KICKCONSE":
            changes = {"faction_council": "0"}
        elif ctx.command == "/RAJAR":
            changes = {
                "faction_id": "neutral",
                "faction_council": "0",
                "faction_prestige": "0",
                "faction_rank": "0",
                "faction_banned_royal": "0",
                "faction_banned_chaos": "0",
                "faction_reward_royal": "0",
                "faction_reward_chaos": "0",
                "faction_change_after": "0",
            }
        else:
            changes = {f"faction_banned_{alignment}": "1"}
            if before.get("faction_id") == alignment:
                changes.update(
                    {
                        "faction_id": "neutral",
                        "faction_council": "0",
                        "faction_prestige": "0",
                        "faction_rank": "0",
                    }
                )
        return Decision({"applied": True}, {key: changes})

    await audited(ctx, (Resource(key, "hash"),), {"target": user, "faction": alignment}, decide)
    sender = ctx.deps.map_manager.get_player_message_sender(user)
    if sender:
        await sender.send_console_msg(
            f"Administración actualizó tu estado de facción ({ctx.command})."
        )
    await ctx.tell("Estado de facción actualizado.")


async def create_clan(ctx: ChatContext) -> None:
    """Funda un clan GM omitiendo sólo nivel/liderazgo, con nombre e índices atómicos.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    name = ctx.arguments.strip()
    if (
        not name
        or len(name) > MAX_CLAN_NAME_LENGTH
        or any(ord(char) < FIRST_PRINTABLE_CHARACTER for char in name)
    ):
        message = f"Uso: /FUNDARCLANGM nombre (hasta {MAX_CLAN_NAME_LENGTH} caracteres)"
        raise ChatCommandError(message)
    clan_id = await ctx.deps.clan_repo.get_next_clan_id()
    account = await ctx.deps.account_repo.get_account_by_user_id(ctx.user) or {}
    clan = Clan(clan_id=clan_id, name=name, leader_id=ctx.user, leader_username=account["username"])
    member = clan.members[ctx.user]
    member.level = int((await ctx.stats()).get("level", 1))
    metadata = asdict(clan)
    metadata.pop("members")
    for field in ("alliances", "wars", "peace_treaties"):
        metadata[field] = list(metadata[field])
    metadata["member_count"] = 1
    record = json.dumps(metadata)
    clan_key, members_key, name_key, user_key = (
        f"clan:{clan_id}",
        f"clan:{clan_id}:members",
        f"clan:name:{name.lower()}",
        f"user:{ctx.user}:clan",
    )
    all_key, index_key = ctx.deps.clan_repo.ALL_CLANS_KEY, ctx.deps.clan_repo.CLAN_INDEX_KEY

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        if (
            snapshot[clan_key]
            or snapshot[name_key]
            or snapshot[user_key]
            or int(stats.get("min_hp", 0)) <= 0
        ):
            return Decision(
                {
                    "applied": False,
                    "message": "El nombre ya existe, ya perteneces a un clan o estás muerto.",
                },
                {},
            )
        ids = set(cast("set[str]", snapshot[index_key]))
        ids.add(str(clan_id))
        return Decision(
            {"applied": True},
            {
                clan_key: record,
                members_key: {str(ctx.user): json.dumps(asdict(member))},
                name_key: str(clan_id),
                user_key: str(clan_id),
                all_key: {str(clan_id): record},
                index_key: ids,
            },
        )

    await audited(
        ctx,
        (
            Resource(ctx.key, "hash"),
            Resource(clan_key, "string"),
            Resource(members_key, "hash"),
            Resource(name_key, "string"),
            Resource(user_key, "string"),
            Resource(all_key, "hash"),
            Resource(index_key, "set"),
        ),
        {"create_clan": clan_id, "name": name},
        decide,
    )
    await ctx.tell(f"Clan {name} creado; eres su fundador.")


async def remove_member(ctx: ChatContext) -> None:
    """Expulsa a un integrante sin conceder al GM una identidad de líder falsa.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    account = await ctx.account(ctx.arguments)
    user = int(account["user_id"])
    clan = await ctx.deps.clan_repo.get_user_clan(user)
    if clan is None:
        message = "El jugador no pertenece a un clan."
        raise ChatCommandError(message)
    key, members_key, user_key = (
        f"clan:{clan.clan_id}",
        f"clan:{clan.clan_id}:members",
        f"user:{user}:clan",
    )
    all_key = ctx.deps.clan_repo.ALL_CLANS_KEY

    def decide(snapshot: Snapshot) -> Decision:
        state = json.loads(str(snapshot[key] or "{}"))
        members = dict(cast("dict[str, str]", snapshot[members_key]))
        if str(user) not in members or int(state.get("leader_id", 0)) == user:
            return Decision(
                {"applied": False, "message": "No pertenece al clan o es su fundador."}, {}
            )
        if snapshot[user_key] != str(clan.clan_id):
            return Decision({"applied": False, "message": "La pertenencia al clan cambió."}, {})
        members.pop(str(user))
        state["member_count"] = len(members)
        encoded = json.dumps(state)
        return Decision(
            {"applied": True},
            {
                key: encoded,
                all_key: {str(clan.clan_id): encoded},
                members_key: members,
                user_key: None,
            },
        )

    await audited(
        ctx,
        (
            Resource(key, "string"),
            Resource(members_key, "hash", replace=True),
            Resource(user_key, "string", deletable=True),
            Resource(all_key, "hash"),
        ),
        {"remove_clan_member": user, "clan": clan.clan_id},
        decide,
    )
    for member_id in clan.members:
        sender = ctx.deps.map_manager.get_player_message_sender(member_id)
        if sender:
            await sender.send_console_msg(
                f"Administración expulsó a {account['username']} del clan {clan.name}."
            )
    await ctx.tell("Integrante expulsado.")


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    **dict.fromkeys(
        ("/ACEPTCONSE", "/ACEPTCONSECAOS", "/KICKCONSE", "/NOCAOS", "/NOREAL", "/RAJAR"),
        faction_admin,
    ),
    "/FUNDARCLANGM": create_clan,
    "/RAJARCLAN": remove_member,
}
