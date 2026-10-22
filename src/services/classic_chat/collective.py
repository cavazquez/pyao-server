"""Compartir criaturas y elecciones de clan con reglas clásicas y commits únicos."""

import json
import time
from collections import Counter
from typing import TYPE_CHECKING, cast

from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.core.dependency_container import DependencyContainer

ELECTION_SECONDS = 86400
MAX_SHARED_OWNERS = 512
ELECTION_INDEX = "clan:active_elections"


async def share(ctx: ChatContext) -> None:
    """Comparte las criaturas con un único jugador y revoca el destinatario anterior.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await ctx.alive()
    previous = int((await ctx.stats()).get("npc_share_with", 0))
    target = await ctx.selected_user() if ctx.command == "/COMPARTIRNPC" else 0
    if target and await ctx.deps.account_repo.is_gm_by_user_id(target):
        message = "No puedes compartir criaturas con administradores."
        raise ChatCommandError(message)
    targets = {user for user in (previous, target) if user}
    target_stats = RedisKeys.player_user_stats(target) if target else ""
    resources = [
        Resource(ctx.key, "hash"),
        *(Resource(f"npc:shared_with:{user}", "set") for user in sorted(targets)),
    ]
    if target_stats:
        resources.append(Resource(target_stats, "hash"))

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        if int(stats.get("npc_share_with", 0)) != previous:
            return Decision(
                {"applied": False, "message": "La selección cambió; vuelve a intentarlo."}, {}
            )
        if target:
            other = cast("dict[str, str]", snapshot[target_stats])
            forbidden = (
                stats.get("criminal") == "1"
                and (stats.get("faction_id") != "chaos" or other.get("faction_id") != "chaos")
            ) or (stats.get("criminal") != "1" and other.get("criminal") == "1")
            owners = cast("set[str]", snapshot[f"npc:shared_with:{target}"])
            if forbidden or len(owners) >= MAX_SHARED_OWNERS:
                return Decision(
                    {"applied": False, "message": "No puedes compartir criaturas con ese jugador."},
                    {},
                )
        writes: dict[str, dict[str, str] | set[str]] = {ctx.key: {"npc_share_with": str(target)}}
        for user in targets:
            key = f"npc:shared_with:{user}"
            owners = set(cast("set[str]", snapshot[key]))
            owners.discard(str(ctx.user))
            if user == target:
                owners.add(str(ctx.user))
            writes[key] = owners
        return Decision(
            {
                "applied": True,
                "message": "Ahora compartes tus criaturas con el objetivo."
                if target
                else "Has dejado de compartir tus criaturas.",
            },
            writes,
        )

    result = await ctx.commit(tuple(resources), {"share_with": target}, decide)
    await ctx.tell(result["message"])
    if result["applied"]:
        name = ctx.deps.map_manager.get_player_username(ctx.user) or str(ctx.user)
        for user in targets:
            sender = ctx.deps.map_manager.get_player_message_sender(user)
            if sender:
                await sender.send_console_msg(
                    f"{name} "
                    + (
                        "ahora comparte sus criaturas contigo."
                        if user == target
                        else "ha dejado de compartir sus criaturas contigo."
                    )
                )


async def election(ctx: ChatContext) -> None:
    """Abre una elección de 24 horas o registra un voto irrevocable por miembro.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    clan = await ctx.deps.clan_repo.get_user_clan(ctx.user)
    if not clan:
        message = "No perteneces a un clan."
        raise ChatCommandError(message)
    key, members_key = f"clan:{clan.clan_id}:election", f"clan:{clan.clan_id}:members"
    before = await ctx.read_hash(key)
    if before.get("active") == "1" and float(before.get("ends", 0)) <= time.time():
        await finish_election(ctx, clan.clan_id)
        before = await ctx.read_hash(key)
    opening = ctx.command == "/ELECCIONES" and ctx.arguments.upper() == "ABRIR"
    if ctx.command == "/ELECCIONES" and not opening:
        await ctx.tell(
            f"Elección abierta hasta {before.get('ends', '')}."
            if before.get("active") == "1"
            else "No hay elecciones abiertas. El líder puede usar /ELECCIONES ABRIR."
        )
        return
    candidate = await ctx.account(ctx.arguments) if not opening else {}
    identifier = operation_id() if opening else before.get("id", "none")
    votes_key = f"clan:{clan.clan_id}:votes:{identifier}"
    clan_key = f"clan:{clan.clan_id}"

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        members = cast("dict[str, str]", snapshot[members_key])
        metadata = json.loads(str(snapshot[clan_key] or "{}"))
        if str(ctx.user) not in members:
            return Decision({"applied": False, "message": "Ya no perteneces al clan."}, {})
        if opening:
            if int(metadata.get("leader_id", 0)) != ctx.user or state.get("active") == "1":
                return Decision(
                    {
                        "applied": False,
                        "message": (
                            "Sólo el líder puede abrir una elección cuando no hay otra activa."
                        ),
                    },
                    {},
                )
            return Decision(
                {
                    "applied": True,
                    "message": "Elecciones abiertas durante 24 horas. Usa /VOTO nombre.",
                },
                {
                    key: {
                        "id": identifier,
                        "active": "1",
                        "ends": str(time.time() + ELECTION_SECONDS),
                    },
                    ELECTION_INDEX: set(cast("set[str]", snapshot[ELECTION_INDEX]))
                    | {str(clan.clan_id)},
                },
            )
        if (
            state.get("active") != "1"
            or state.get("id") != identifier
            or float(state.get("ends", 0)) <= time.time()
        ):
            return Decision(
                {"applied": False, "message": "No hay elecciones abiertas en tu clan."}, {}
            )
        votes = cast("dict[str, str]", snapshot[votes_key])
        if str(ctx.user) in votes:
            return Decision(
                {"applied": False, "message": "Ya has votado; no puedes cambiar tu voto."}, {}
            )
        if candidate.get("user_id") not in members:
            return Decision(
                {"applied": False, "message": "El candidato no pertenece a tu clan."}, {}
            )
        return Decision(
            {"applied": True, "message": "Voto contabilizado."},
            {votes_key: {str(ctx.user): candidate["user_id"]}},
        )

    result = await ctx.commit(
        (
            Resource(key, "hash"),
            Resource(members_key, "hash"),
            Resource(clan_key, "string"),
            Resource(votes_key, "hash"),
            Resource(ELECTION_INDEX, "set"),
        ),
        {"clan": clan.clan_id, "open": opening, "candidate": candidate.get("user_id", "")},
        decide,
    )
    await ctx.tell(result["message"])


async def finish_election(ctx: ChatContext, clan_id: int) -> None:
    """Cierra una elección vencida y cambia el líder sólo ante un ganador único."""
    await finish_election_for(ctx.deps, clan_id)


async def finish_election_for(deps: DependencyContainer, clan_id: int) -> None:
    """Liquida un plazo aunque todos los integrantes estén desconectados."""
    redis = deps.redis_client.redis
    key = f"clan:{clan_id}:election"
    before = cast("dict[str, str]", await redis.hgetall(key))
    if before.get("active") != "1" or float(before.get("ends", 0)) > time.time():
        return
    votes_key, clan_key, members_key = (
        f"clan:{clan_id}:votes:{before['id']}",
        f"clan:{clan_id}",
        f"clan:{clan_id}:members",
    )
    all_clans = deps.clan_repo.ALL_CLANS_KEY

    def decide(snapshot: Snapshot) -> Decision:
        current = cast("dict[str, str]", snapshot[key])
        if (
            current.get("id") != before["id"]
            or current.get("active") != "1"
            or float(current.get("ends", 0)) > time.time()
        ):
            return Decision({"applied": False}, {})
        members = cast("dict[str, str]", snapshot[members_key])
        votes = cast("dict[str, str]", snapshot[votes_key])
        counts = Counter(
            candidate
            for voter, candidate in votes.items()
            if voter in members and candidate in members
        )
        maximum = max(counts.values(), default=0)
        winners = [user for user, count in counts.items() if count == maximum]
        active = set(cast("set[str]", snapshot[ELECTION_INDEX]))
        active.discard(str(clan_id))
        writes: dict[str, str | dict[str, str] | set[str]] = {
            key: {
                "active": "0",
                "result": "tie" if len(winners) > 1 else "empty" if not winners else winners[0],
            },
            ELECTION_INDEX: active,
        }
        message = (
            "La elección terminó en empate; se conserva el líder."
            if len(winners) > 1
            else "La elección terminó sin votos válidos."
        )
        if len(winners) == 1 and snapshot[clan_key]:
            clan = json.loads(str(snapshot[clan_key]))
            winner = json.loads(members[winners[0]])
            updated = dict(members)
            for user in {str(clan["leader_id"]), winners[0]} & members.keys():
                member = json.loads(members[user])
                updated[user] = json.dumps({**member, "rank": 4 if user == winners[0] else 3})
            message = f"{winner['username']} ganó la elección del clan."
            clan.update(
                {
                    "leader_id": int(winners[0]),
                    "leader_username": winner["username"],
                    "news": message,
                }
            )
            encoded = json.dumps(clan)
            writes.update(
                {clan_key: encoded, all_clans: {str(clan_id): encoded}, members_key: updated}
            )
        return Decision({"applied": True, "message": message}, writes)

    await require_durable(redis)
    result = await transact(
        redis,
        (
            Resource(key, "hash"),
            Resource(votes_key, "hash"),
            Resource(clan_key, "string"),
            Resource(members_key, "hash"),
            Resource(all_clans, "hash"),
            Resource(ELECTION_INDEX, "set"),
        ),
        operation_id(),
        {"finish_election": clan_id, "id": before["id"]},
        decide,
    )
    await require_durable(redis)
    if result.get("applied"):
        group = await deps.clan_repo.get_clan(clan_id)
        if group:
            for user in group.members:
                sender = deps.map_manager.get_player_message_sender(user)
                if sender:
                    await sender.send_console_msg(result["message"])


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/COMPARTIRNPC": share,
    "/NOCOMPARTIRNPC": share,
    "/VOTO": election,
    "/ELECCIONES": election,
}
