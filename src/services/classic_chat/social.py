"""Canales privados, asistencia y consultas clásicas con permisos actuales."""

import hmac
import json
import secrets
import time
from operator import itemgetter
from typing import TYPE_CHECKING, cast

from src.network.chat_channel import deliver_chat
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

MAX_INQUIRY_COMPONENTS = 9
MAX_OPTION_LENGTH = 120
MAX_QUESTION_LENGTH = 200
MAX_SENTINEL_ATTEMPTS = 5
MIN_INQUIRY_COMPONENTS = 3

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

MAX_REPORT = 400


async def clan_message(ctx: ChatContext) -> None:
    """Envía /CMSG mediante el canal de clan autorizado existente.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if not ctx.arguments:
        message = "Uso: /CMSG mensaje"
        raise ChatCommandError(message)
    error = await ctx.deps.clan_service.send_clan_message(ctx.user, ctx.arguments)
    if error:
        await ctx.tell(error)


async def online_group(ctx: ChatContext) -> None:
    """Expone sólo los miembros del grupo o clan del actor.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if ctx.command == "/ONLINEPARTY":
        party = await ctx.deps.party_service.get_party_info(ctx.user)
        members = list(party.members) if party else []
    else:
        clan = await ctx.deps.clan_repo.get_user_clan(ctx.user)
        members = list(clan.members) if clan else []
    if not members:
        message = "No perteneces a ese grupo."
        raise ChatCommandError(message)
    names = [ctx.deps.map_manager.get_player_username(user) for user in members]
    present = [name for name in names if name]
    await ctx.tell(f"Conectados ({len(present)}): " + (", ".join(present) or "ninguno"))


async def report(ctx: ChatContext) -> None:
    """Guarda solicitudes y avisos para GM sin divulgar su contenido al mapa.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    kind = {"/GM": "help", "/ROL": "role", "/_BUG": "bug", "/DENUNCIAR": "denounce"}[ctx.command]
    if kind == "denounce" and (await ctx.stats()).get("denounces_muted") == "1":
        await ctx.tell("Tus denuncias están silenciadas; puedes pedir ayuda con /GM.")
        return
    if ctx.command != "/GM" and not ctx.arguments:
        message = f"Uso: {ctx.command} mensaje"
        raise ChatCommandError(message)
    if len(ctx.arguments) > MAX_REPORT:
        message = "El mensaje es demasiado largo."
        raise ChatCommandError(message)
    key = f"chat:reports:{kind}"
    identifier = str(ctx.user) if kind == "help" else secrets.token_hex(16)
    value = json.dumps({"user": ctx.user, "text": ctx.arguments, "at": int(time.time())})
    result = await ctx.commit(
        (Resource(key, "hash"),),
        {"kind": kind, "id": identifier},
        lambda _snapshot: Decision(
            {"applied": True, "message": "Tu solicitud ha sido registrada."},
            {key: {identifier: value}},
        ),
    )
    await ctx.tell(result["message"])
    name = ctx.deps.map_manager.get_player_username(ctx.user) or str(ctx.user)
    for user in ctx.deps.map_manager.get_all_connected_user_ids():
        if await ctx.deps.account_repo.is_gm_by_user_id(user):
            if (
                kind == "denounce"
                and await ctx.redis.hget(RedisKeys.player_user_stats(user), "gm_denounces") == "0"
            ):
                continue
            sender = ctx.deps.map_manager.get_player_message_sender(user)
            if sender:
                await sender.send_console_msg(f"{kind.upper()} de {name}: {ctx.arguments}")


async def consultation(ctx: ChatContext) -> None:
    """Alterna la consulta entre un GM y un jugador próximo, nunca otro GM.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    target = await ctx.selected_user()
    if target == ctx.user or await ctx.deps.account_repo.is_gm_by_user_id(target):
        message = "Selecciona un jugador que no sea administrador."
        raise ChatCommandError(message)
    key = RedisKeys.player_user_stats(target)

    def decide(snapshot: Snapshot) -> Decision:
        before = cast("dict[str, str]", snapshot[key])
        active = before.get("consultation") == str(ctx.user)
        return Decision(
            {"applied": True, "message": "Consulta terminada." if active else "Consulta iniciada."},
            {
                key: {
                    "consultation": "0" if active else str(ctx.user),
                    "hidden_until": "0",
                    "invisible_until": "0",
                }
            },
        )

    result = await ctx.commit((Resource(key, "hash"),), {"target": target}, decide)
    await ctx.tell(result["message"])
    sender = ctx.deps.map_manager.get_player_message_sender(target)
    if sender and result["applied"]:
        await sender.send_console_msg(result["message"])
        await sender.status_effects.sync_visibility(
            target, ctx.deps.player_repo, ctx.deps.map_manager
        )


async def penalties(ctx: ChatContext) -> None:
    """Consulta el historial público de penas sin exponer datos de cuentas GM.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    account = await ctx.account(ctx.arguments)
    target = int(account["user_id"])
    if account.get("is_gm") == "1" and not ctx.gm:
        message = "No puedes consultar las penas de administradores."
        raise ChatCommandError(message)
    records = await ctx.read_hash(f"moderation:penalties:{target}")
    rows = [
        {**entry, "identity": identity}
        for identity, record in records.items()
        if not (entry := json.loads(record)).get("removed")
    ]
    rows.sort(key=itemgetter("at"), reverse=True)
    await ctx.tell(
        "\n".join(
            f"{record['identity'] + ': ' if ctx.gm else ''}{record['kind']}: {record['reason']}"
            for record in rows[:30]
        )
        or "Sin prontuario."
    )


async def inquiry(ctx: ChatContext) -> None:
    """Consulta una encuesta activa o confirma un voto por personaje y encuesta.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    key = "world:inquiry"
    verb, _space, remaining = ctx.arguments.partition(" ")
    if verb.upper() in {"CREAR", "CERRAR"}:
        if not ctx.gm:
            message = "Sólo un GM puede administrar encuestas."
            raise ChatCommandError(message)
        identifier = secrets.token_hex(16)
        if verb.upper() == "CREAR":
            pieces = [part.strip() for part in remaining.split("|")]
            if (
                not MIN_INQUIRY_COMPONENTS <= len(pieces) <= MAX_INQUIRY_COMPONENTS
                or not all(pieces)
                or len(pieces[0]) > MAX_QUESTION_LENGTH
                or any(len(part) > MAX_OPTION_LENGTH for part in pieces[1:])
            ):
                message = "Uso: /ENCUESTA CREAR pregunta|opción 1|opción 2[|más opciones]"
                raise ChatCommandError(message)

            def open_inquiry(snapshot: Snapshot) -> Decision:
                current = cast("dict[str, str]", snapshot[key])
                if current.get("active") == "1":
                    return Decision(
                        {
                            "applied": False,
                            "message": "Cierra la encuesta actual antes de abrir otra.",
                        },
                        {},
                    )
                return Decision(
                    {"applied": True, "message": "Encuesta creada."},
                    {
                        key: {
                            "active": "1",
                            "id": identifier,
                            "question": pieces[0],
                            "options": json.dumps(pieces[1:]),
                        }
                    },
                )

            result = await ctx.commit(
                (Resource(key, "hash"),), {"inquiry": "open", "id": identifier}, open_inquiry
            )
        else:
            result = await ctx.commit(
                (Resource(key, "hash"),),
                {"inquiry": "close"},
                lambda _snapshot: Decision(
                    {"applied": True, "message": "Encuesta cerrada."}, {key: {"active": "0"}}
                ),
            )
        await ctx.tell(result["message"])
        return
    state = await ctx.read_hash(key)
    if not state or state.get("active") != "1":
        await ctx.tell("No hay una encuesta activa.")
        return
    options = json.loads(state.get("options", "[]"))
    if not ctx.arguments:
        await ctx.tell(
            state["question"]
            + "\n"
            + "\n".join(f"{i + 1}. {value}" for i, value in enumerate(options))
        )
        return
    vote = integer(ctx.arguments, 1, len(options))
    votes = f"world:inquiry:{state['id']}:votes"

    def decide(snapshot: Snapshot) -> Decision:
        current = cast("dict[str, str]", snapshot[key])
        previous = cast("dict[str, str]", snapshot[votes])
        if current.get("id") != state["id"] or current.get("active") != "1":
            return Decision({"applied": False, "message": "La encuesta ya terminó."}, {})
        if str(ctx.user) in previous:
            return Decision({"applied": False, "message": "Ya has votado en esta encuesta."}, {})
        return Decision(
            {"applied": True, "message": "Voto registrado."}, {votes: {str(ctx.user): str(vote)}}
        )

    result = await ctx.commit(
        (Resource(key, "hash"), Resource(votes, "hash")), {"vote": vote}, decide
    )
    await ctx.tell(result["message"])


async def council_message(ctx: ChatContext) -> None:
    """Publica sólo a consejeros de la misma facción y a administradores.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    stats = await ctx.stats()
    faction = stats.get("faction_id", "neutral")
    if (
        not ctx.arguments
        or not (ctx.gm or stats.get("faction_council") == "1")
        or faction not in {"royal", "chaos"}
    ):
        message = "Sólo el consejo de una facción puede usar /BMSG mensaje."
        raise ChatCommandError(message)
    username = ctx.deps.map_manager.get_player_username(ctx.user) or str(ctx.user)
    for user in ctx.deps.map_manager.get_all_connected_user_ids():
        other = await ctx.read_hash(RedisKeys.player_user_stats(user))
        allowed = other.get("faction_id") == faction and other.get("faction_council") == "1"
        if allowed or await ctx.deps.account_repo.is_gm_by_user_id(user):
            sender = ctx.deps.map_manager.get_player_message_sender(user)
            if sender:
                await deliver_chat(
                    sender,
                    "system",
                    ctx.user,
                    username,
                    ctx.arguments,
                    legacy=f"Consejo {username}: {ctx.arguments}",
                    context=f"council:{faction}",
                )


async def sentinel(ctx: ChatContext) -> None:
    """Responde a un desafío persistido, vigente y ligado al personaje."""
    code = integer(ctx.arguments, 1, 32767)
    key = f"security:sentinel:{ctx.user}"

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        if (
            state.get("answered") != "0"
            or float(state.get("until", 0)) <= time.time()
            or int(state.get("attempts", 0)) >= MAX_SENTINEL_ATTEMPTS
        ):
            return Decision(
                {"applied": False, "message": "Código incorrecto o desafío vencido."}, {}
            )
        if not hmac.compare_digest(state.get("code", ""), str(code)):
            return Decision(
                {"applied": False, "message": "Código incorrecto o desafío vencido."},
                {key: {"attempts": str(int(state.get("attempts", 0)) + 1)}},
            )
        return Decision(
            {"applied": True, "message": "El centinela ha confirmado tu presencia."},
            {key: {"answered": "1", "code": ""}},
        )

    result = await ctx.commit((Resource(key, "hash", keep_ttl=True),), {"reply": True}, decide)
    await ctx.tell(result["message"])


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/CMSG": clan_message,
    "/ONLINECLAN": online_group,
    "/ONLINEPARTY": online_group,
    "/GM": report,
    "/ROL": report,
    "/_BUG": report,
    "/DENUNCIAR": report,
    "/CONSULTA": consultation,
    "/PENAS": penalties,
    "/ENCUESTA": inquiry,
    "/BMSG": council_message,
    "/CENTINELA": sentinel,
}
