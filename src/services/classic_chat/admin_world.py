"""Edición del mundo como overlays Redis; conserva los mapas binarios originales."""

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.services.classic_chat.admin_common import audited, tile
from src.services.classic_chat.context import ChatCommandError, ChatContext, integer
from src.services.classic_chat.world_rules import WORLD_REVISION
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GroundState, stack_identity
from src.utils.ground_storage import position_fields, read_ground
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot

AREA_RADIUS = 10
ITEM_ARGUMENTS = 2
MAP_SIDE = 100
MAX_DIALOG_LENGTH = 400
MAX_SAVED_DIALOG_LENGTH = 4096
MAX_MAP_FIELD_LENGTH = 80
MAX_RESPAWN_SECONDS = 86400
MAX_SAVED_NPCS = 512
PORTAL_ARGUMENTS = 4

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from src.core.dependency_container import DependencyContainer

PORTAL_ITEM = 651


async def load_overlays(deps: DependencyContainer) -> None:
    """Reconstruye overlays por mapas conocidos sin SCAN ni modificar los binarios.

    Raises:
        ValueError: Si los datos o precondiciones de la operación son inválidos.
    """
    redis = deps.redis_client.redis
    for map_id in range(1, 291):
        if not deps.map_manager.has_map(map_id):
            continue
        rows = cast("dict[str, str]", await redis.hgetall(f"world:map:tiles:{map_id}"))
        for coordinate, encoded in rows.items():
            x, y = map(int, coordinate.split(","))
            if not 1 <= x <= MAP_SIDE or not 1 <= y <= MAP_SIDE:
                message = "Overlay de mapa fuera de límites"
                raise ValueError(message)
            deps.map_manager.tile_overrides[map_id, x, y] = json.loads(encoded)
            deps.map_manager.overlay_positions.setdefault(map_id, set()).add((x, y))
        deps.map_manager.map_overrides[map_id] = cast(
            "dict[str, str]", await redis.hgetall(f"world:map:rules:{map_id}")
        )


async def restore_saved_maps(deps: DependencyContainer) -> None:
    """Restaura los checkpoints de configuración sin tocar cuentas, oro ni mascotas.

    Raises:
        ValueError: Si los datos o precondiciones de la operación son inválidos.
    """
    redis = deps.redis_client.redis
    for map_id in range(1, 291):
        saved = await redis.get(f"world:map:saved:{map_id}")
        if not saved:
            await redis.hset(f"world:pretorians:{map_id}", "active", "0")
            continue
        checkpoint = json.loads(saved)
        rows = checkpoint.get("npcs")
        valid = (
            checkpoint.get("version") == 1
            and checkpoint.get("map") == map_id
            and deps.map_manager.has_map(map_id)
            and isinstance(rows, list)
            and len(rows) <= MAX_SAVED_NPCS
            and all(
                isinstance(row, dict)
                and type(row.get("id")) is int
                and deps.npc_catalog.get_npc_data(row["id"])
                and all(
                    type(row.get(field)) is int and 1 <= row[field] <= MAP_SIDE
                    for field in ("x", "y")
                )
                and type(row.get("respawn")) is int
                and 0 <= row["respawn"] <= MAX_RESPAWN_SECONDS
                and row.get("heading") in {1, 2, 3, 4}
                and row.get("role") in {"inhabitant", "creature", "guard", "pretorian", "training"}
                and (
                    "description" not in row
                    or (
                        isinstance(row["description"], str)
                        and len(row["description"]) <= MAX_SAVED_DIALOG_LENGTH
                    )
                )
                for row in rows
            )
        )
        if not valid:
            message = f"Checkpoint de configuración inválido para mapa {map_id}"
            raise ValueError(message)
        for existing_npc in list(deps.map_manager.get_npcs_in_map(map_id)):
            if not existing_npc.is_tamed and not existing_npc.summoned_by_user_id:
                await deps.npc_service.remove_npc(existing_npc)
        for row in rows:
            x, y = row["x"], row["y"]
            if not deps.map_manager.can_move_to(map_id, x, y):
                locations = [
                    (x + dx, y + dy)
                    for radius in range(1, 6)
                    for dx in range(-radius, radius + 1)
                    for dy in range(-radius, radius + 1)
                    if max(abs(dx), abs(dy)) == radius
                    and deps.map_manager.can_move_to(map_id, x + dx, y + dy)
                ]
                if not locations:
                    message = f"No hay espacio para restaurar un NPC del mapa {map_id}"
                    raise ValueError(message)
                x, y = locations[0]
            npc = await deps.npc_service.spawn_npc(row["id"], map_id, x, y, row["heading"])
            if npc is None:
                message = f"No se pudo restaurar un NPC del mapa {map_id}"
                raise ValueError(message)
            npc.respawn_time = npc.respawn_time_max = row["respawn"]
            npc.role = row["role"]
            if "description" in row:
                npc.description = row["description"]
            await redis.hset(
                RedisKeys.npc_instance(npc.instance_id),
                mapping={
                    "role": npc.role,
                    "description": npc.description,
                    "respawn_time": str(npc.respawn_time),
                    "respawn_time_max": str(npc.respawn_time_max),
                },
            )
        await redis.hset(
            f"world:pretorians:{map_id}",
            "active",
            "1" if any(row["role"] == "pretorian" for row in rows) else "0",
        )


async def publish_tile(ctx: ChatContext, map_id: int, x: int, y: int) -> None:
    """Publica colisión y gráfico del portal a los jugadores del mapa."""
    state = ctx.deps.map_manager.tile_overrides.get((map_id, x, y), {})
    for sender in ctx.deps.map_manager.get_all_message_senders_in_map(map_id):
        if "blocked" in state:
            await sender.send_block_position(x, y, bool(state["blocked"]))
        if "portal" in state:
            if state["portal"]:
                graphic = ctx.deps.item_catalog.get_grh_index(PORTAL_ITEM) or 0
                await sender.send_object_create(x, y, graphic)
            else:
                await sender.send_object_delete(x, y)


async def overlay(ctx: ChatContext) -> None:
    """Edita colisión, trigger o portal y usa el mismo overlay para jugar y guardar.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    map_id, x, y = await tile(ctx)
    key = f"world:map:tiles:{map_id}"
    coordinate = f"{x},{y}"
    update: dict[str, Any] = {}
    if ctx.command == "/CT":
        pos = await ctx.position()
        map_id, x, y = pos["map"], pos["x"], pos["y"] - 1
        if y < 1:
            message = "No hay una casilla al norte del personaje."
            raise ChatCommandError(message)
        key, coordinate = f"world:map:tiles:{map_id}", f"{x},{y}"
        parts = ctx.arguments.replace(",", " ").split()
        if len(parts) not in {3, 4}:
            message = "Uso: /CT mapa x y [radio de 0 a 6]"
            raise ChatCommandError(message)
        target, tx, ty = (
            integer(parts[0], 1, 290),
            integer(parts[1], 1, 100),
            integer(parts[2], 1, 100),
        )
        radius = integer(parts[3], 0, 6) if len(parts) == PORTAL_ARGUMENTS else 0
        if (
            not ctx.deps.map_manager.has_map(target)
            or not ctx.deps.map_manager.can_move_to(target, tx, ty)
            or ctx.deps.map_manager.get_exit_tile(target, tx, ty)
            or not ctx.deps.map_manager.can_move_to(map_id, x, y)
            or ctx.deps.map_manager.get_exit_tile(map_id, x, y)
        ):
            message = "El origen o el destino está bloqueado, ocupado o ya tiene un portal."
            raise ChatCommandError(message)
        update = {"portal": {"to_map": target, "to_x": tx, "to_y": ty, "radius": radius}}
    elif ctx.command == "/DT":
        if not ctx.deps.map_manager.get_exit_tile(map_id, x, y):
            message = "Selecciona un portal."
            raise ChatCommandError(message)
        update = {"portal": None}
    elif ctx.command == "/TRIGGER":
        current = ctx.deps.map_manager.tile_overrides.get((map_id, x, y), {})
        if not ctx.arguments:
            await ctx.tell(f"Trigger de {map_id}:{x},{y}: {current.get('trigger', 0)}")
            return
        update = {"trigger": integer(ctx.arguments, 0, 6)}
    elif ctx.command == "/BLOQ":
        if ctx.deps.map_manager.is_tile_occupied(map_id, x, y):
            message = "No puedes cambiar la colisión de una casilla ocupada."
            raise ChatCommandError(message)
        update = {"blocked": not ctx.deps.map_resources_service.is_blocked(map_id, x, y)}

    def decide(snapshot: Snapshot) -> Decision:
        rows = cast("dict[str, str]", snapshot[key])
        previous = json.loads(rows.get(coordinate, "{}"))
        result = {**previous, **update}
        return Decision(
            {"applied": True, "overlay": result},
            {
                key: {coordinate: json.dumps(result)},
                WORLD_REVISION: str(int(str(snapshot[WORLD_REVISION] or "0")) + 1),
            },
        )

    result = await audited(
        ctx,
        (Resource(key, "hash"), Resource(WORLD_REVISION, "string")),
        {"map": map_id, "x": x, "y": y, "change": update},
        decide,
    )
    ctx.deps.map_manager.tile_overrides[map_id, x, y] = result["overlay"]
    ctx.deps.map_manager.overlay_positions.setdefault(map_id, set()).add((x, y))
    await publish_tile(ctx, map_id, x, y)
    await ctx.tell("Mapa actualizado y persistido en Redis.")


async def ground(ctx: ChatContext) -> None:
    """Crea o retira objetos mediante el mismo commit y caché de las transferencias."""
    pos = await ctx.position()
    map_id, x, y = pos["map"], pos["x"], pos["y"]
    if ctx.command == "/LIMPIAR":
        count = 0
        for target in range(1, 291):
            if ctx.deps.map_manager.has_map(target):
                count += await ground_map(ctx, target, x, y)
        await ctx.tell(f"Retirados {count} stack(s) de todos los mapas; los portales se conservan.")
    else:
        count = await ground_map(ctx, map_id, x, y)
        await ctx.tell(
            f"{'Creado' if ctx.command == '/CI' else 'Retirados'} {count} stack(s) del suelo."
        )


async def ground_map(ctx: ChatContext, map_id: int, x: int, y: int) -> int:
    """Confirma un mapa por operación; el vaciado global tolera reanudaciones.

    Returns:
        Cantidad de stacks creados o retirados.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    item_id, quantity = 0, 0
    scope: tuple[tuple[int, int], ...]
    if ctx.command == "/CI":
        parts = ctx.arguments.split()
        if len(parts) not in {1, 2}:
            message = "Uso: /CI objeto [cantidad, por defecto 100]"
            raise ChatCommandError(message)
        item_id = integer(parts[0], 1, 32767)
        quantity = integer(parts[1], 1, 1000) if len(parts) == ITEM_ARGUMENTS else 100
        y -= 1
        if y < 1 or ctx.deps.item_catalog.get_item_data(item_id) is None:
            message = "Objeto o casilla inválidos."
            raise ChatCommandError(message)
        scope = ((x, y),)
    else:
        state = await read_ground(ctx.redis, map_id)
        scope = tuple(
            (px, py)
            for px, py in state.positions()
            if not ctx.deps.map_manager.get_exit_tile(map_id, px, py)
            and (
                ctx.command == "/LIMPIAR"
                or (ctx.command == "/MASSDEST" and max(abs(px - x), abs(py - y)) <= AREA_RADIUS)
                or (ctx.command == "/DEST" and (px, py) == (x, y))
            )
        )
        if not scope:
            return 0
    if any(ctx.deps.map_manager.get_exit_tile(map_id, px, py) for px, py in scope):
        message = "Usa /DT para retirar portales."
        raise ChatCommandError(message)
    key, identity = RedisKeys.ground_items(map_id), operation_id()

    def decide(snapshot: Snapshot) -> Decision:
        state = GroundState(map_id, cast("str | None", snapshot[key]))
        count = sum(len(state.tile(px, py)) for px, py in scope)
        if item_id:
            state.append(
                x,
                y,
                {
                    "item_id": item_id,
                    "quantity": quantity,
                    "grh_index": ctx.deps.item_catalog.get_grh_index(item_id) or 0,
                    "stack_id": stack_identity(identity),
                    "owner_id": ctx.user,
                    "spawn_time": int(time.time()),
                },
            )
        else:
            for px, py in scope:
                state.tiles[f"{px},{py}"] = []
        return Decision(
            {
                "applied": True,
                "count": 1 if item_id else count,
                "ground_positions": [list(p) for p in scope],
            },
            {key: state.encode()},
        )

    result = await ctx.deps.map_manager.apply_ground_operation(
        map_id,
        x,
        y,
        ctx.redis,
        lambda: audited(
            ctx,
            (Resource(key, "ground", fields=position_fields(scope)),),
            {"ground": map_id, "item": item_id, "quantity": quantity, "scope": list(scope)},
            decide,
        ),
        broadcast_service=ctx.deps.broadcast_service,
        operation_id=identity,
        ground_positions=scope,
    )
    return int(result["count"])


async def map_info(ctx: ChatContext) -> None:
    """Modifica reglas explícitas; no permite rutas, claves Redis ni código libre.

    Raises:
        ChatCommandError: Si los datos o precondiciones de la operación son inválidos.
    """
    parts = ctx.arguments.split(maxsplit=1)
    pos = await ctx.position()
    key = f"world:map:rules:{pos['map']}"
    if not parts:
        await ctx.tell(json.dumps(await ctx.read_hash(key), ensure_ascii=False))
        return
    if len(parts) != ITEM_ARGUMENTS:
        message = "Uso: /MODMAPINFO atributo valor"
        raise ChatCommandError(message)
    aliases = {
        "nombre": "name",
        "music": "music",
        "musica": "music",
        "seguro": "safe",
        "pk": "safe",
        "backup": "backup",
        "magiasinefecto": "no_magic",
        "invisinefecto": "no_invisible",
        "resusinefecto": "no_revive",
        "restringir": "restriction",
        "terreno": "terrain",
        "zona": "zone",
        "robo": "no_steal",
        "robonpc": "allow_npc_steal",
        "ocultarsinefecto": "no_hide",
        "invocarsinefecto": "no_summon",
    }
    field = aliases.get(parts[0].lower())
    value = parts[1].strip()
    if field is None or not value or len(value) > MAX_MAP_FIELD_LENGTH:
        message = (
            "Atributos: NOMBRE, MUSIC, PK, SEGURO, BACKUP, MAGIASINEFECTO, "
            "INVISINEFECTO, RESUSINEFECTO, RESTRINGIR, TERRENO, ZONA, ROBO, "
            "ROBONPC, OCULTARSINEFECTO, INVOCARSINEFECTO."
        )
        raise ChatCommandError(message)
    if field in {
        "safe",
        "no_magic",
        "no_invisible",
        "no_revive",
        "no_steal",
        "backup",
        "allow_npc_steal",
        "no_hide",
        "no_summon",
    }:
        value = str(integer(value, 0, 1))
        if parts[0].lower() == "pk":
            value = "0" if value == "1" else "1"
    elif field == "music":
        value = str(integer(value, 0, 255))
    elif field == "restriction":
        value = value.upper()
        if value not in {"NO", "NEWBIE", "ARMADA", "CAOS", "FACCION"}:
            message = "Restricciones: NO, NEWBIE, ARMADA, CAOS, FACCION."
            raise ChatCommandError(message)
    elif field in {"terrain", "zone"}:
        choices = {
            "BOSQUE": "wilderness",
            "NIEVE": "snow",
            "DESIERTO": "desert",
            "CIUDAD": "city",
            "CAMPO": "field",
            "DUNGEON": "dungeon",
            "INTERIOR": "building",
            "AGUA": "water",
        }
        value = choices.get(value.upper(), value.lower())
        if value not in choices.values():
            message = (
                "Terreno/zona: BOSQUE, NIEVE, DESIERTO, CIUDAD, CAMPO, DUNGEON, INTERIOR, AGUA."
            )
            raise ChatCommandError(message)
    saved_key = f"world:map:saved:{pos['map']}"
    await audited(
        ctx,
        (
            Resource(key, "hash"),
            Resource(WORLD_REVISION, "string"),
            Resource(saved_key, "string", deletable=True),
        ),
        {"map": pos["map"], "field": field},
        lambda snapshot: Decision(
            {"applied": True},
            {
                key: {field: value},
                WORLD_REVISION: str(int(str(snapshot[WORLD_REVISION] or "0")) + 1),
                **({saved_key: None} if field == "backup" and value == "0" else {}),
            },
        ),
    )
    ctx.deps.map_manager.map_overrides.setdefault(pos["map"], {})[field] = value
    if field == "music":
        for sender in ctx.deps.map_manager.get_all_message_senders_in_map(pos["map"]):
            await sender.send_play_midi(int(value))
    elif field == "backup" and value == "1":
        await save_map(ctx)
    await ctx.tell(f"Mapa {pos['map']}: {field} = {value}.")


def checkpoint(deps: DependencyContainer, map_id: int) -> str:
    """Serializa configuración estable; excluye mascotas y criaturas temporales.

    Returns:
        Checkpoint JSON versionado para restauración al arrancar.
    """
    npcs = [
        {
            "id": npc.npc_id,
            "x": npc.x,
            "y": npc.y,
            "heading": npc.heading,
            "respawn": npc.respawn_time,
            "role": npc.role,
            "description": npc.description,
        }
        for npc in deps.map_manager.get_npcs_in_map(map_id)
        if not npc.is_tamed
        and not npc.summoned_by_user_id
        and npc.role != "training"
        and (npc.max_hp == 0 or npc.hp > 0)
    ]
    return json.dumps({"version": 1, "map": map_id, "at": int(time.time()), "npcs": npcs})


async def save_map(ctx: ChatContext) -> None:
    """Guarda checkpoint y NPC del mapa para restaurarlos al reiniciar."""
    pos = await ctx.position()
    key = f"world:map:saved:{pos['map']}"
    record = checkpoint(ctx.deps, pos["map"])
    await audited(
        ctx,
        (Resource(key, "string"),),
        {"save_map": pos["map"]},
        lambda _snapshot: Decision({"applied": True}, {key: record}),
    )
    await ctx.tell(
        f"Checkpoint del mapa {pos['map']} guardado en Redis; los binarios originales se conservan."
    )


HANDLERS: dict[str, Callable[[ChatContext], Awaitable[None]]] = {
    **dict.fromkeys(("/CT", "/DT", "/TRIGGER", "/BLOQ"), overlay),
    **dict.fromkeys(("/CI", "/DEST", "/MASSDEST", "/LIMPIAR"), ground),
    "/GUARDAMAPA": save_map,
    "/MODMAPINFO": map_info,
}
