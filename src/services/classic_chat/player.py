"""Acciones clásicas del personaje con persistencia y objetivos validados."""

import secrets
import time
from typing import TYPE_CHECKING, cast

from src.command_handlers.left_click_npc_handler import LeftClickNPCHandler
from src.models.item_constants import MAX_PLAYER_GOLD
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.services.classic_chat.factions import npc_service
from src.services.world.pets import PetOrders
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

BANK_RANGE = 3

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

PRIESTS = frozenset({81, 82, 119})
GAMBLERS = frozenset({104})
GOVERNORS = frozenset({13, 150, 151, 152, 153, 158})
MAX_BET = 5000
WIN_PERCENT = 47
DESCRIPTION_LIMIT = 255


async def description(ctx: ChatContext) -> None:
    """Actualiza la descripción propia sin emitir el antiguo paquete inválido.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await ctx.alive()
    if len(ctx.arguments) > DESCRIPTION_LIMIT:
        message = "La descripción no puede superar 255 caracteres."
        raise ChatCommandError(message)

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        if int(stats.get("min_hp", 0)) <= 0:
            return Decision({"applied": False, "message": "¡Estás muerto!"}, {})
        return Decision(
            {"applied": True, "message": "Descripción actualizada."},
            {ctx.key: {"description": ctx.arguments}},
        )

    result = await ctx.commit((Resource(ctx.key, "hash"),), {}, decide)
    await ctx.tell(result["message"])


async def bank(ctx: ChatContext) -> None:
    """Consulta el saldo o abre la bóveda del banquero seleccionado.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await ctx.alive()
    npc = await ctx.npc()
    position = await ctx.position()
    if (
        not npc.is_banker
        or max(abs(npc.x - position["x"]), abs(npc.y - position["y"])) > BANK_RANGE
    ):
        message = "Debes seleccionar un banquero y acercarte a él."
        raise ChatCommandError(message)
    if ctx.command == "/BALANCE":
        gold = await ctx.deps.bank_repo.get_gold(ctx.user)
        await ctx.sender.send_update_bank_gold(gold)
        await ctx.tell(f"Tienes {gold} monedas de oro en tu cuenta.")
        return
    interaction = LeftClickNPCHandler(
        ctx.deps.merchant_repo, ctx.deps.bank_repo, ctx.deps.redis_client, ctx.sender
    )
    await interaction.handle_npc_click(ctx.user, npc)


async def pets(ctx: ChatContext) -> None:
    """Comparte las órdenes clásicas con el mismo servicio de la ventana de mascotas."""
    await ctx.alive()
    order = {"/QUIETO": "wait", "/ACOMPAÑAR": "follow", "/LIBERAR": "release"}[ctx.command]
    service = PetOrders(ctx.deps.npc_service)
    changed = 0
    for pet in service.snapshot(ctx.user)["pets"]:
        result = await service.command(ctx.user, pet["id"], order, operation_id())
        changed += int(bool(result["applied"]))
    await require_durable(ctx.redis)
    await ctx.tell(f"Orden aplicada a {changed} mascota(s).")


async def priest(ctx: ChatContext) -> None:
    """Reutiliza la resurrección confirmada y cura sólo ante un sacerdote próximo.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    npc = await ctx.npc()
    if npc.npc_id not in PRIESTS:
        message = "Debes seleccionar un sacerdote."
        raise ChatCommandError(message)
    stats = await ctx.stats()
    if ctx.command == "/RESUCITAR" or int(stats.get("min_hp", 0)) <= 0:
        if ctx.deps.player_death_service:
            await ctx.deps.player_death_service.revive_player(ctx.user, ctx.sender, priest=npc)
        return

    def decide(snapshot: Snapshot) -> Decision:
        current = cast("dict[str, str]", snapshot[ctx.key])
        if int(current.get("min_hp", 0)) <= 0:
            return Decision({"applied": False, "message": "Debes resucitar primero."}, {})
        return Decision(
            {"applied": True, "hp": int(current.get("max_hp", 0)), "message": "¡Has sido curado!"},
            {ctx.key: {"min_hp": current.get("max_hp", "0")}},
        )

    result = await ctx.commit_near(
        npc, (Resource(ctx.key, "hash"),), {"priest": npc.instance_id}, decide, distance=2
    )
    if result["applied"]:
        await ctx.sender.send_update_hp(result["hp"])
    await ctx.tell(result["message"])


async def rest(ctx: ChatContext) -> None:
    """Alterna el descanso sólo junto a una fogata viva y registra su posición."""
    await ctx.alive()
    position = await ctx.position()
    position_key = RedisKeys.player_position(ctx.user)
    fires = tuple(
        Resource(
            f"world:campfire:{position['map']}:{position['x'] + dx}:{position['y'] + dy}", "hash"
        )
        for dx in range(-1, 2)
        for dy in range(-1, 2)
    )

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        active = stats.get("resting") == "1"
        actual = cast("dict[str, str]", snapshot[position_key])
        same_position = all(
            int(actual.get(field, -1)) == position[field] for field in ("map", "x", "y")
        )
        if (
            not same_position
            or int(stats.get("min_hp", 0)) <= 0
            or (not active and not any(snapshot[r.key] for r in fires))
        ):
            return Decision(
                {"applied": False, "message": "Necesitas estar vivo y junto a una fogata."}, {}
            )
        return Decision(
            {
                "applied": True,
                "message": "Te levantas." if active else "Comienzas a descansar junto a la fogata.",
            },
            {
                ctx.key: {
                    "resting": "0" if active else "1",
                    "rest_map": str(position["map"]),
                    "rest_x": str(position["x"]),
                    "rest_y": str(position["y"]),
                }
            },
        )

    result = await ctx.commit(
        (Resource(ctx.key, "hash"), Resource(position_key, "hash"), *fires), {}, decide
    )
    if result["applied"]:
        await ctx.sender.status_effects.sync_status(ctx.user, ctx.deps.player_repo)
    await ctx.tell(result["message"])


async def gamble(ctx: ChatContext) -> None:
    """Casino clásico: apuesta de 1 a 5000, 47% de victoria y saldo indivisible."""
    await ctx.alive()
    npc = await ctx.npc()
    npc_service(npc, "gambler")
    amount = integer(ctx.arguments, 1, MAX_BET)
    won = secrets.randbelow(100) < WIN_PERCENT
    ledger = "economy:casino"

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[ctx.key])
        account = cast("dict[str, str]", snapshot[ledger])
        gold = int(stats.get("gold", 0))
        if (
            int(stats.get("min_hp", 0)) <= 0
            or gold < amount
            or (won and gold + amount > MAX_PLAYER_GOLD)
        ):
            return Decision(
                {"applied": False, "message": "No tienes oro suficiente o excederías el máximo."},
                {},
            )
        balance = gold + (amount if won else -amount)
        field = "paid" if won else "received"
        return Decision(
            {
                "applied": True,
                "gold": balance,
                "won": won,
                "message": f"Has {'ganado' if won else 'perdido'} {amount} monedas de oro.",
            },
            {
                ctx.key: {"gold": str(balance)},
                ledger: {
                    "rounds": str(int(account.get("rounds", 0)) + 1),
                    field: str(int(account.get(field, 0)) + amount),
                },
            },
        )

    result = await ctx.commit_near(
        npc, (Resource(ctx.key, "hash"), Resource(ledger, "hash")), {"amount": amount}, decide
    )
    if result["applied"]:
        await ctx.sender.send_update_gold(result["gold"])
    await ctx.tell(result["message"])


async def home(ctx: ChatContext) -> None:
    """Establece hogar ante un gobernador o regresa como fantasma tras la espera.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    position = await ctx.position()
    try:
        npc = await ctx.npc()
    except ValueError:
        npc = None
    stats = await ctx.stats()
    if npc and npc.npc_id in GOVERNORS and int(stats.get("min_hp", 0)) > 0:
        row = npc_service(npc, "governor")
        if int(stats.get("min_hp", 0)) <= 0:
            message = "Debes estar vivo para obtener la ciudadanía."
            raise ChatCommandError(message)
        account = await ctx.deps.account_repo.get_account_by_user_id(ctx.user) or {}
        spawn = await ctx.read_hash(RedisKeys.home_spawn(int(row["home"])))
        if not spawn or not ctx.deps.map_manager.has_map(int(spawn.get("map", 0))):
            message = "La ciudad no tiene un punto de hogar válido."
            raise ChatCommandError(message)
        account_key = RedisKeys.account_data(account["username"])
        result = await ctx.commit_near(
            npc,
            (Resource(ctx.key, "hash"), Resource(account_key, "hash")),
            {"home": row["home"]},
            lambda snapshot: (
                Decision(
                    {"applied": True, "message": "Este lugar es ahora tu hogar."},
                    {
                        account_key: {"char_home": str(row["home"])},
                        ctx.key: {
                            "home_map": spawn["map"],
                            "home_x": spawn["x"],
                            "home_y": spawn["y"],
                        },
                    },
                )
                if int(cast("dict[str, str]", snapshot[ctx.key]).get("min_hp", 0)) > 0
                else Decision(
                    {"applied": False, "message": "Debes estar vivo para obtener ciudadanía."}, {}
                )
            ),
        )
        await ctx.tell(result["message"])
        return
    if int(stats.get("min_hp", 0)) > 0 or float(stats.get("jail_until", 0)) > time.time():
        message = "Debes estar muerto y fuera de la cárcel para regresar al hogar."
        raise ChatCommandError(message)
    account = await ctx.deps.account_repo.get_account_by_user_id(ctx.user) or {}
    spawn = await ctx.read_hash(RedisKeys.home_spawn(int(account.get("char_home", 1))))
    destination = (
        int(stats.get("home_map", spawn.get("map", 1))),
        int(stats.get("home_x", spawn.get("x", 50))),
        int(stats.get("home_y", spawn.get("y", 50))),
    )
    if destination[0] == position["map"]:
        await ctx.tell("Ya te encuentras en tu hogar.")
        return
    # The tick service confirms the delayed transfer; repeated commands cancel it.

    def decide(snapshot: Snapshot) -> Decision:
        current = cast("dict[str, str]", snapshot[ctx.key])
        if int(current.get("min_hp", 0)) > 0 or float(current.get("jail_until", 0)) > time.time():
            return Decision(
                {
                    "applied": False,
                    "message": "Debes estar muerto y fuera de la cárcel para regresar al hogar.",
                },
                {},
            )
        active = float(current.get("home_due", 0)) > 0
        return Decision(
            {
                "applied": True,
                "message": "Regreso cancelado."
                if active
                else "Regresarás a tu hogar en 60 segundos. Escribe /HOGAR para cancelar.",
            },
            {
                ctx.key: {
                    "home_due": "0" if active else str(time.time() + 60),
                    "home_map": str(destination[0]),
                    "home_x": str(destination[1]),
                    "home_y": str(destination[2]),
                }
            },
        )

    result = await ctx.commit((Resource(ctx.key, "hash"),), {"home": True}, decide)
    await ctx.tell(result["message"])


async def train(ctx: ChatContext) -> None:
    """Consulta o solicita una criatura del entrenador del mapa.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    await ctx.alive()
    npc = await ctx.npc()
    creatures = cast("list[int]", npc_service(npc, "trainer")["creatures"])
    catalog = ctx.deps.npc_catalog
    if not creatures:
        message = "Debes seleccionar un entrenador de criaturas."
        raise ChatCommandError(message)
    if not ctx.arguments:
        names = [
            f"{index + 1}. {(catalog.get_npc_data(value) or {}).get('nombre', 'Criatura')}"
            for index, value in enumerate(creatures)
        ]
        await ctx.tell("Entrenamiento: /ENTRENAR número\n" + "\n".join(names))
        return
    choice = creatures[integer(ctx.arguments, 1, len(creatures)) - 1]
    if npc.map_id in ctx.deps.map_manager.training_maps or any(
        pet.role == "training" for pet in ctx.deps.map_manager.get_npcs_in_map(npc.map_id)
    ):
        message = "Ya hay una criatura de entrenamiento en este mapa."
        raise ChatCommandError(message)
    ctx.deps.map_manager.training_maps.add(npc.map_id)
    reservation = operation_id()
    try:
        valid = await ctx.commit_near(
            npc,
            (Resource(ctx.key, "hash"),),
            {"train": choice},
            lambda snapshot: Decision(
                {"applied": int(cast("dict[str, str]", snapshot[ctx.key]).get("min_hp", 0)) > 0}, {}
            ),
        )
        if not valid["applied"]:
            await ctx.tell(str(valid.get("message", "Debes estar vivo para entrenar.")))
            return
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            if ctx.deps.map_manager.can_move_to(npc.map_id, npc.x + dx, npc.y + dy):
                ctx.deps.map_manager.reserve_positions(
                    reservation, npc.map_id, [(npc.x + dx, npc.y + dy)]
                )
                spawned = await ctx.deps.npc_service.spawn_npc(
                    choice,
                    npc.map_id,
                    npc.x + dx,
                    npc.y + dy,
                    reservation=reservation,
                    role="training",
                    respawn_seconds=0,
                )
                if spawned:
                    await ctx.tell(f"El entrenador ha liberado un {spawned.name}.")
                    return
    finally:
        ctx.deps.map_manager.release_positions(reservation)
        ctx.deps.map_manager.training_maps.discard(npc.map_id)
    message = "No hay una casilla libre junto al entrenador."
    raise ChatCommandError(message)


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    "/DESC": description,
    "/BALANCE": bank,
    "/BOVEDA": bank,
    "/QUIETO": pets,
    "/ACOMPAÑAR": pets,
    "/LIBERAR": pets,
    "/RESUCITAR": priest,
    "/CURAR": priest,
    "/DESCANSAR": rest,
    "/APOSTAR": gamble,
    "/HOGAR": home,
    "/ENTRENAR": train,
}
