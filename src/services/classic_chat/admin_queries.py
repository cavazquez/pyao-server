"""Consultas y mensajes GM con listas de campos explícitas y audiencia limitada."""

from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from src.models.skills import skill_progress
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.utils.redis_config import RedisKeys

SLOT_ARGUMENTS = 2

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

STATS_FIELDS = (
    "level",
    "min_hp",
    "max_hp",
    "min_mana",
    "max_mana",
    "min_sta",
    "max_sta",
    "experience",
    "kills",
    "deaths",
    "jail_until",
    "faction_id",
    "faction_prestige",
)


async def character(ctx: ChatContext) -> None:
    """Consulta una cuenta sólo después de la autorización GM del despacho."""
    account = await ctx.account(ctx.arguments)
    user = int(account["user_id"])
    name = account["username"]
    stats = await ctx.read_hash(RedisKeys.player_user_stats(user))
    if ctx.command == "/BAL":
        gold = await ctx.deps.bank_repo.get_gold(user)
        await ctx.tell(f"{name}: bolsillo {stats.get('gold', '0')}; banco {gold}.")
    elif ctx.command in {"/INV", "/BOV"}:
        if ctx.command == "/INV":
            bag = await ctx.deps.inventory_repo.get_inventory_slots(user)
            stacks = [(slot, item.item_id, item.quantity) for slot, item in sorted(bag.items())]
        else:
            items = await ctx.deps.bank_repo.get_all_items(user)
            stacks = [(item.slot, item.item_id, item.quantity) for item in items]
        rows = [
            f"{slot}: {ctx.deps.item_catalog.get_item_name(item_id) or item_id} x{quantity}"
            for slot, item_id, quantity in stacks
        ]
        await ctx.tell(name + ":\n" + ("\n".join(rows) or "Vacío."))
    elif ctx.command == "/SKILLS":
        skills = await ctx.read_hash(RedisKeys.player_skills(user))
        await ctx.tell(
            name
            + ":\n"
            + "\n".join(f"{p.definition.key}: {p.level}" for p in skill_progress(skills))
        )
    elif ctx.command == "/LASTEMAIL":
        await ctx.tell(f"{name}: {account.get('email', 'Sin correo registrado')}")
    elif ctx.command in {"/LASTIP", "/NICK2IP"}:
        sender = ctx.deps.map_manager.get_player_message_sender(user)
        address = sender.connection.address[0] if sender else account.get("last_ip", "Desconocida")
        await ctx.tell(f"{name}: {address}")
    elif ctx.command == "/STAT":
        await ctx.tell(
            name + ":\n" + "\n".join(f"{key}: {stats.get(key, '0')}" for key in STATS_FIELDS)
        )
    else:
        position = await ctx.deps.player_repo.get_position(user) or {}
        fields = {
            key: account.get(key, "")
            for key in ("username", "user_id", "char_race", "char_home", "is_gm")
        }
        await ctx.tell(
            "\n".join(f"{key}: {value}" for key, value in {**fields, **position}.items())
            + f"\nDescripción: {stats.get('description', '')}"
        )


async def online(ctx: ChatContext) -> None:
    """Filtra jugadores conectados sin recorrer Redis completo ni divulgar claves."""
    names = []
    position = await ctx.position()
    for user, name, map_id in ctx.deps.map_manager.get_all_online_players():
        stats = await ctx.read_hash(RedisKeys.player_user_stats(user))
        include = (
            (ctx.command == "/ONLINEGM" and await ctx.deps.account_repo.is_gm_by_user_id(user))
            or (
                ctx.command == "/ONLINEMAP"
                and map_id
                == (integer(ctx.arguments, 1, 32767) if ctx.arguments else position["map"])
            )
            or (ctx.command == "/ONLINEREAL" and stats.get("faction_id") == "royal")
            or (ctx.command == "/ONLINECAOS" and stats.get("faction_id") == "chaos")
        )
        if include:
            names.append(name)
    await ctx.tell(f"Conectados ({len(names)}): " + (", ".join(names) or "ninguno"))


async def where(ctx: ChatContext) -> None:
    """Muestra la posición autoritativa del jugador nombrado."""
    account = await ctx.account(ctx.arguments)
    position = await ctx.deps.player_repo.get_position(int(account["user_id"]))
    await ctx.tell(f"{account['username']}: {position or 'Sin posición registrada'}")


async def server_time(ctx: ChatContext) -> None:
    """Muestra fecha y hora UTC del reloj autoritativo del servidor."""
    await ctx.tell(datetime.now(UTC).strftime("Hora del servidor: %Y-%m-%d %H:%M:%S UTC"))


async def creatures(ctx: ChatContext) -> None:
    """Cuenta criaturas del mapa actual o enumera una página del catálogo.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    catalog = ctx.deps.npc_catalog
    if ctx.command == "/CC":
        page = integer(ctx.arguments or "1", 1, 1000)
        ids = ctx.deps.npc_catalog.get_all_npc_ids()
        chunk = sorted(ids)[(page - 1) * 20 : page * 20]
        await ctx.tell(
            f"Catálogo NPC, página {page}:\n"
            + "\n".join(
                f"{identifier}: {(catalog.get_npc_data(identifier) or {}).get('nombre', 'NPC')}"
                for identifier in chunk
            )
        )
        return
    position = await ctx.position()
    map_id = integer(ctx.arguments, 1, 290) if ctx.arguments else position["map"]
    if not ctx.deps.map_manager.has_map(map_id):
        message = "Mapa desconocido."
        raise ChatCommandError(message)
    counts = Counter(npc.name for npc in ctx.deps.map_manager.get_npcs_in_map(map_id))
    await ctx.tell(
        f"NPC del mapa {map_id}: "
        + (", ".join(f"{name} x{count}" for name, count in counts.items()) or "ninguno")
    )


async def floor(ctx: ChatContext) -> None:
    """Cuenta los objetos del mapa utilizando el índice del mundo."""
    position = await ctx.position()
    count = ctx.deps.map_manager.get_ground_items_count(position["map"])
    await ctx.tell(f"Objetos en el suelo del mapa {position['map']}: {count}.")


async def clan(ctx: ChatContext) -> None:
    """Consulta miembros de un clan concreto y su conexión actual.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    group = await ctx.deps.clan_repo.get_clan_by_name(ctx.arguments)
    if not group:
        message = "Clan no encontrado."
        raise ChatCommandError(message)
    rows = [
        member.username
        for user, member in group.members.items()
        if ctx.command == "/MIEMBROSCLAN" or ctx.deps.map_manager.get_player_message_sender(user)
    ]
    await ctx.tell(group.name + ": " + (", ".join(rows) or "ninguno"))


async def broadcast(ctx: ChatContext) -> None:
    """Publica sólo a la audiencia correspondiente al comando administrativo.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    if not ctx.arguments:
        message = f"Uso: {ctx.command} mensaje"
        raise ChatCommandError(message)
    position = await ctx.position()
    operator = ctx.deps.map_manager.get_player_username(ctx.user) or "GM"
    sent = 0
    for user, _name, map_id in ctx.deps.map_manager.get_all_online_players():
        stats = await ctx.read_hash(RedisKeys.player_user_stats(user))
        allowed = (
            ctx.command in {"/RMSG", "/SMSG"}
            or (ctx.command == "/MAPMSG" and map_id == position["map"])
            or (ctx.command == "/GMSG" and await ctx.deps.account_repo.is_gm_by_user_id(user))
            or (ctx.command == "/REALMSG" and stats.get("faction_id") == "royal")
            or (ctx.command == "/CAOSMSG" and stats.get("faction_id") == "chaos")
            or (ctx.command == "/CIUMSG" and stats.get("criminal") != "1")
            or (ctx.command == "/CRIMSG" and stats.get("criminal") == "1")
        )
        sender = ctx.deps.map_manager.get_player_message_sender(user)
        if allowed and sender:
            await sender.send_console_msg(f"[{operator}] {ctx.arguments}")
            sent += 1
    await ctx.tell(f"Mensaje enviado a {sent} jugador(es).")


async def ip_users(ctx: ChatContext) -> None:
    """Resuelve conexiones activas de una IP sin exponerlas a jugadores comunes."""
    import ipaddress  # ruff: ignore[import-outside-top-level]

    address = str(ipaddress.ip_address(ctx.arguments))
    names = []
    for user, name, _map in ctx.deps.map_manager.get_all_online_players():
        sender = ctx.deps.map_manager.get_player_message_sender(user)
        if sender and sender.connection.address[0] == address:
            names.append(name)
    await ctx.tell(", ".join(names) or "No hay jugadores conectados desde esa IP.")


async def slots(ctx: ChatContext) -> None:
    """Consulta el objeto de un slot de inventario concreto, como /SLOT clásico.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split()
    if len(parts) != SLOT_ARGUMENTS:
        message = "Uso: /SLOT nombre número"
        raise ChatCommandError(message)
    account = await ctx.account(parts[0])
    slot = integer(parts[1], 1, 30)
    items = await ctx.deps.inventory_repo.get_inventory_slots(int(account["user_id"]))
    item = items.get(slot)
    await ctx.tell(
        f"Slot {slot}: {ctx.deps.item_catalog.get_item_name(item.item_id)} x{item.quantity}"
        if item
        else f"Slot {slot}: vacío."
    )


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    **dict.fromkeys(
        ("/INFO", "/STAT", "/BAL", "/INV", "/BOV", "/SKILLS", "/LASTEMAIL", "/LASTIP", "/NICK2IP"),
        character,
    ),
    **dict.fromkeys(("/ONLINEGM", "/ONLINEMAP", "/ONLINEREAL", "/ONLINECAOS"), online),
    **dict.fromkeys(
        ("/RMSG", "/SMSG", "/MAPMSG", "/GMSG", "/REALMSG", "/CAOSMSG", "/CIUMSG", "/CRIMSG"),
        broadcast,
    ),
    "/DONDE": where,
    "/HORA": server_time,
    "/NENE": creatures,
    "/CC": creatures,
    "/PISO": floor,
    "/ONCLAN": clan,
    "/MIEMBROSCLAN": clan,
    "/IP2NICK": ip_users,
    "/SLOT": slots,
}
