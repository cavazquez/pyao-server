"""Recolección: recurso, intento y entrenamiento se confirman en el mismo EXEC."""

import math
import random
import time
from typing import TYPE_CHECKING, Any, cast

from src.models.skills import skill_progress
from src.services.fishing_zones import FishingZones
from src.services.skill_training import trained_decision, training_resources
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

MAX_COORD = 100
FISHING_SKILL = 12


if TYPE_CHECKING:
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

GATHERING = {
    9: ("talar", 561, 58, 5, "Leña", 6),
    13: ("mineria", 562, 192, 3, "Mineral de Hierro", 5),
    12: ("pesca", 563, 139, 2, "Pescado", 6),
}

GATHERING_TOOLS = {9: frozenset({127, 561}), 13: frozenset({187, 562}), 12: frozenset({138, 563})}


async def gather(
    player: PlayerRepository,
    inventory: InventoryRepository,
    resources: MapResourcesService,
    user_id: int,
    skill_id: int,
    map_id: int,
    x: int,
    y: int,
    *,
    identity: str | None = None,
) -> dict[str, Any]:
    """Valida el intento y no entrega recursos sin confirmar inventario y progreso.

    Returns:
        Resultado autoritativo, incluido éxito/fallo válido sin confundirlo con rechazo.
    """
    if skill_id not in GATHERING:
        return {"applied": False, "message": "Habilidad de recolección inválida."}
    key, _tool, item, quantity, name, winning_rolls = GATHERING[skill_id]
    sample = random.random()
    fish_choice: tuple[int, str, int] | None = None
    inventory_key, position_key = (
        RedisKeys.player_inventory(user_id),
        RedisKeys.player_position(user_id),
    )

    def decide(snapshot: Snapshot) -> Decision:  # ruff: ignore[too-many-locals] - recurso, pesca y XP atómicos
        nonlocal fish_choice
        position = cast("dict[str, str]", snapshot[position_key])
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user_id)])
        if (
            int(stats.get("min_hp", 0)) <= 0
            or int(position.get("map", 0)) != map_id
            or max(abs(int(position.get("x", -1)) - x), abs(int(position.get("y", -1)) - y)) > 1
            or not 1 <= x <= MAX_COORD
            or not 1 <= y <= MAX_COORD
        ):
            return Decision(
                {"applied": False, "message": "Debes estar vivo y junto al recurso."}, {}
            )
        queries = {9: resources.has_tree, 13: resources.has_mine, 12: resources.has_water}
        if not queries[skill_id](map_id, x, y):
            return Decision(
                {"applied": False, "message": "No hay un recurso apropiado en esa casilla."}, {}
            )
        slots = SlotPlan(
            cast("dict[str, str]", snapshot[inventory_key]),
            int(inventory.MAX_SLOTS),
            inventory.stacking.max_stack,
        )
        equipment = cast("dict[str, str]", snapshot[RedisKeys.player_equipment(user_id)])
        weapon = slots.slots.get(int(equipment.get("weapon", 0)))
        if weapon is None or weapon.item_id not in GATHERING_TOOLS[skill_id]:
            return Decision(
                {"applied": False, "message": "No tienes la herramienta necesaria."}, {}
            )
        skills = cast("dict[str, str]", snapshot[RedisKeys.player_skills(user_id)])
        catch_item, catch_name = item, name
        band, coast_distance = "", 0
        if skill_id == FISHING_SKILL:
            zones = getattr(resources, "fishing_zones", None)
            if not isinstance(zones, FishingZones):
                zones = FishingZones(resources)
                resources.fishing_zones = zones
            if fish_choice is None:
                fish_choice = zones.catch((map_id, x, y))
            catch_item, band, coast_distance = fish_choice
            catch_name = {139: "Pescado", 544: "Pez Dorado", 545: "Pez Espada", 546: "Merluza"}.get(
                catch_item, "Pescado"
            )
        level = next(p.level for p in skill_progress(skills) if p.definition.key == key)
        luck = max(1, math.floor(-0.00125 * level * level - 0.3 * level + 49))
        successful = sample < min(1.0, winning_rolls / luck)
        try:
            # También comprueba capacidad en un fallo válido: no entrenar con bolsa llena.
            slots.give(catch_item, quantity)
        except ValueError as error:
            return Decision({"applied": False, "message": str(error)}, {})
        decision = Decision(
            {
                "applied": True,
                "successful": successful,
                "quantity": quantity if successful else 0,
                "item_id": catch_item,
                "fishing_band": band,
                "coast_distance": coast_distance,
                "skill": key,
                "message": f"Has obtenido {quantity} {catch_name}."
                if successful
                else f"No has obtenido {catch_name}; sigues practicando.",
            },
            {
                RedisKeys.player_user_stats(user_id): {
                    "work_last_at": str(time.time()),
                    "work_skill": key,
                },
                **({inventory_key: slots.fields()} if successful else {}),
            },
        )
        return trained_decision(decision, snapshot, user_id, ((key, successful),))

    watched = tuple(
        {
            r.key: r
            for r in (
                *training_resources(user_id),
                Resource(inventory_key, "hash"),
                Resource(RedisKeys.player_equipment(user_id), "hash"),
                Resource(position_key, "hash"),
            )
        }.values()
    )
    return await transact(
        player.redis.redis,
        watched,
        identity or operation_id(),
        {"gather": user_id, "skill": skill_id, "map": map_id, "x": x, "y": y},
        decide,
    )
