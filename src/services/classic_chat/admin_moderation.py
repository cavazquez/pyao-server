"""Bloqueos, cárcel y desconexiones con identidad y estado persistente."""

import asyncio
import ipaddress
import json
import time
from typing import TYPE_CHECKING, cast

from src.security.ip_bans import IP_BANS_KEY
from src.services.account_moderation import AccountModeration
from src.services.classic_chat.admin_character import nearby, warp
from src.services.classic_chat.admin_common import audited, fields
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

IP_ARGUMENTS = 2
JAIL_ARGUMENTS = 3
MAX_REASON_LENGTH = 120

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

JAIL_MAP = 66


async def ip_ban(ctx: ChatContext) -> None:
    """Administra IPs reales; el login y las conexiones leen el mismo registro.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if ctx.command in {"/BANIPLIST", "/BANIPRELOAD"}:
        entries = await ctx.read_hash(IP_BANS_KEY)
        valid = []
        for address, encoded in entries.items():
            ipaddress.ip_address(address)
            record = json.loads(encoded)
            if record.get("active"):
                valid.append(address)
        if ctx.command == "/BANIPRELOAD":
            await ctx.tell(
                f"Verificados {len(entries)} registros IP. "
                "Se consultan directamente en Redis en cada conexión/login."
            )
        else:
            page = integer(ctx.arguments or "1", 1, max(1, (len(valid) + 19) // 20))
            await ctx.tell(
                f"IPs bloqueadas, página {page}: "
                + (", ".join(sorted(valid)[(page - 1) * 20 : page * 20]) or "ninguna")
            )
        return
    parts = ctx.arguments.split(maxsplit=1)
    if not parts:
        message = f"Uso: {ctx.command} IP|nombre [motivo]"
        raise ChatCommandError(message)
    try:
        address = str(ipaddress.ip_address(parts[0]))
    except ValueError:
        account = await ctx.account(parts[0])
        sender = ctx.deps.map_manager.get_player_message_sender(int(account["user_id"]))
        address = str(
            ipaddress.ip_address(
                sender.connection.address[0] if sender else account.get("last_ip", "")
            )
        )
    reason = parts[1] if len(parts) == IP_ARGUMENTS else "Moderación del servidor"
    if len(reason) > MAX_REASON_LENGTH:
        message = "El motivo no puede superar 120 caracteres."
        raise ChatCommandError(message)
    active = ctx.command == "/BANIP"
    own = str(ipaddress.ip_address(ctx.sender.connection.address[0]))
    if active and address == own:
        message = "No puedes bloquear la IP de tu propia conexión."
        raise ChatCommandError(message)
    record = json.dumps(
        {"active": active, "until": 0, "actor": ctx.user, "at": int(time.time()), "reason": reason}
    )
    await fields(ctx, IP_BANS_KEY, {address: record})
    if active:
        for user in ctx.deps.map_manager.get_all_connected_user_ids():
            sender = ctx.deps.map_manager.get_player_message_sender(user)
            if sender and str(ipaddress.ip_address(sender.connection.address[0])) == address:
                sender.connection.close()
    await ctx.tell("IP bloqueada." if active else "Bloqueo IP revocado.")


async def jail(ctx: ChatContext) -> None:
    """Persiste plazo offline y retorno; traslada a una casilla válida de la cárcel.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split("@")
    if len(parts) != JAIL_ARGUMENTS or not parts[1].strip() or len(parts[1]) > MAX_REASON_LENGTH:
        message = "Uso: /CARCEL nombre@motivo@minutos (0 a 1440; 0 libera)"
        raise ChatCommandError(message)
    account = await ctx.account(parts[0].strip())
    user = int(account["user_id"])
    minutes = integer(parts[2], 0, 1440)
    if account.get("is_gm") == "1":
        message = "No puedes encarcelar administradores."
        raise ChatCommandError(message)
    position = await ctx.deps.player_repo.get_position(user)
    if position is None or ctx.deps.map_manager.get_player_message_sender(user) is None:
        message = "El personaje debe estar conectado."
        raise ChatCommandError(message)
    if not ctx.deps.map_manager.has_map(JAIL_MAP):
        message = "No está disponible el mapa de la cárcel de Banderbill."
        raise ChatCommandError(message)
    x, y = nearby(ctx, JAIL_MAP, 50, 50)
    key, penalties = RedisKeys.player_user_stats(user), f"moderation:penalties:{user}"
    identity, now = operation_id(), time.time()

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        remaining = float(state.get("jail_until", 0)) > now
        origin = {
            f"jail_return_{field}": state.get(f"jail_return_{field}", str(position[field]))
            if remaining
            else str(position[field])
            for field in ("map", "x", "y")
        }
        return Decision(
            {"applied": True},
            {
                key: {
                    "jail_until": str(now + minutes * 60),
                    "jail_pending_return": "1",
                    "home_due": "0",
                    **origin,
                },
                penalties: {
                    identity: json.dumps(
                        {
                            "kind": "cárcel",
                            "reason": parts[1],
                            "minutes": minutes,
                            "actor": ctx.user,
                            "at": int(now),
                        }
                    )
                },
            },
        )

    await audited(
        ctx,
        (Resource(key, "hash"), Resource(penalties, "hash")),
        {"target": user, "minutes": minutes},
        decide,
    )
    if minutes:
        await warp(ctx, account["username"], JAIL_MAP, x, y)
    sender = ctx.deps.map_manager.get_player_message_sender(user)
    if sender:
        await sender.send_console_msg(
            f"Has sido encarcelado durante {minutes} minutos. Motivo: {parts[1]}"
        )
    await ctx.tell(
        "Condena registrada y traslado completado."
        if minutes
        else "Liberación registrada; el traslado se completará en el próximo tick."
    )


async def kick_all(ctx: ChatContext) -> None:
    """Drena y cierra las conexiones de jugadores, conservando a los operadores."""
    await audited(
        ctx, (), {"kick": "all_players"}, lambda _snapshot: Decision({"applied": True}, {})
    )
    count = 0
    for user in ctx.deps.map_manager.get_all_connected_user_ids():
        if await ctx.deps.account_repo.is_gm_by_user_id(user):
            continue
        sender = ctx.deps.map_manager.get_player_message_sender(user)
        if sender:
            await sender.send_console_msg("El administrador ha desconectado a los jugadores.")
            try:
                async with asyncio.timeout(1):
                    await sender.connection.flush()
            except TimeoutError, ConnectionError:
                pass
            sender.connection.close()
            count += 1
    await ctx.tell(f"Desconectados {count} jugadores.")


async def ban_clan(ctx: ChatContext) -> None:
    """Bloquea las cuentas del clan y conserva la prohibición de admisión al clan.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    clan = await ctx.deps.clan_repo.get_clan_by_name(ctx.arguments)
    if clan is None:
        message = "Clan no encontrado."
        raise ChatCommandError(message)
    if any(member.user_id == ctx.user for member in clan.members.values()):
        message = "No puedes bloquear tu propio clan."
        raise ChatCommandError(message)
    await fields(ctx, f"clan:{clan.clan_id}:ban", {"active": "1", "actor": str(ctx.user)})
    count = 0
    moderation = AccountModeration(ctx.deps.account_repo)
    for member in clan.members.values():
        result = await moderation.apply(
            ctx.user,
            member.username,
            active=True,
            days=0,
            reason=f"Clan bloqueado: {clan.name}"[:120],
        )
        count += int(bool(result.get("applied")))
    await ctx.tell(f"Clan bloqueado; cuentas bloqueadas: {count}/{len(clan.members)}.")


async def security(ctx: ChatContext) -> None:
    """Muestra un resumen sin credenciales ni configuraciones de conexión privadas."""
    bans = await ctx.read_hash(IP_BANS_KEY)
    await ctx.tell(
        f"Seguridad: {len(ctx.deps.map_manager.get_all_connected_user_ids())} sesiones de juego; "
        f"{sum(bool(json.loads(value).get('active')) for value in bans.values())} IP bloqueadas.\n"
        "Los permisos se verifican en el servidor; las mutaciones GM registran auditoría en Redis."
    )


async def centinel(ctx: ChatContext) -> None:
    """Alterna el worker de desafíos y conserva los resultados de los anteriores."""
    key = "security:sentinel:policy"

    def decide(snapshot: Snapshot) -> Decision:
        state = cast("dict[str, str]", snapshot[key])
        active = state.get("active") != "1"
        return Decision(
            {"applied": True, "active": active},
            {key: {"active": "1" if active else "0", "next_at": "0"}},
        )

    result = await audited(ctx, (Resource(key, "hash"),), {"sentinel": True}, decide)
    await ctx.tell("Centinela activado." if result["active"] else "Centinela desactivado.")


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    **dict.fromkeys(("/BANIP", "/UNBANIP", "/BANIPLIST", "/BANIPRELOAD"), ip_ban),
    "/CARCEL": jail,
    "/BANCLAN": ban_clan,
    "/ECHARTODOSPJS": kick_all,
    "/DUMPSECURITY": security,
    "/CENTINELAACTIVADO": centinel,
}
