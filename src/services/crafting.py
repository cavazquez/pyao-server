"""Fabricación autoritativa y atómica sobre recetas e inventario de Redis."""

import json
import math
import random
from typing import TYPE_CHECKING, Any, cast

from src.models.crafting_data_loader import CRAFTING_KEY
from src.models.skills import skill_progress
from src.services.skill_training import trained_decision, training_resources
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

CRAFT_TOOLS = {"herreria": (389, 565), "carpinteria": (198, 564), "mineria": ()}
MAX_CRAFT_QUANTITY = 100


def nearby_station(resources: MapResourcesService, position: dict[str, str], skill: str) -> bool:
    """Exige taller cercano para herrería y fragua para fundir minerales.

    Returns:
        Si el entorno permite fabricar con esta habilidad.
    """
    if skill == "carpinteria":
        return True
    map_id, x, y = (int(position.get(field, 0)) for field in ("map", "x", "y"))
    query = resources.has_anvil if skill == "herreria" else resources.has_forge
    return any(query(map_id, tx, ty) for tx in range(x - 1, x + 2) for ty in range(y - 1, y + 2))


def consume_materials(slots: SlotPlan, materials: list[dict[str, int]], quantity: int) -> None:
    """Retira materiales completos de varios stacks antes de aceptar el resultado.

    Raises:
        ValueError: Si falta una parte de cualquier material.
    """
    for material in materials:
        needed = material["quantity"] * quantity
        for slot, stack in list(slots.slots.items()):
            if stack.item_id == material["item_id"]:
                taken = min(needed, stack.quantity)
                slots.take(slot, stack.item_id, taken)
                needed -= taken
                if not needed:
                    break
        if needed:
            message = f"Faltan materiales: objeto {material['item_id']}."
            raise ValueError(message)


async def craft(
    player: PlayerRepository,
    inventory: InventoryRepository,
    resources: MapResourcesService,
    user_id: int,
    recipe_id: str,
    quantity: int,
    *,
    identity: str | None = None,
) -> dict[str, Any]:
    """Confirma gasto, resultado y entrenamiento juntos y sin duplicar reintentos.

    Returns:
        Resultado persistido del intento o rechazo sin consumo.
    """
    if type(quantity) is not int or not 1 <= quantity <= MAX_CRAFT_QUANTITY:
        return {"applied": False, "message": "Cantidad inválida (1 a 100)."}
    sample = random.random()
    inv_key, pos_key = RedisKeys.player_inventory(user_id), RedisKeys.player_position(user_id)

    def decide(snapshot: Snapshot) -> Decision:
        recipes = json.loads(str(snapshot.get(CRAFTING_KEY) or "[]"))
        recipe = next((r for r in recipes if r["id"] == recipe_id), None)
        if recipe is None:
            return Decision({"applied": False, "message": "Receta desconocida."}, {})
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user_id)])
        skill = recipe["skill"]
        skills = cast("dict[str, str]", snapshot[RedisKeys.player_skills(user_id)])
        level = next(p.level for p in skill_progress(skills) if p.definition.key == skill)
        position = cast("dict[str, str]", snapshot[pos_key])
        if int(stats.get("min_hp", 0)) <= 0 or level < recipe["required"]:
            return Decision(
                {
                    "applied": False,
                    "message": f"Debes estar vivo y tener {recipe['required']} de {skill}.",
                },
                {},
            )
        if not nearby_station(resources, position, skill):
            return Decision(
                {"applied": False, "message": "Debes estar junto al taller apropiado."}, {}
            )
        slots = SlotPlan(
            cast("dict[str, str]", snapshot[inv_key]),
            inventory.MAX_SLOTS,
            inventory.stacking.max_stack,
        )
        tools = CRAFT_TOOLS[skill]
        if tools and not any(s.item_id in tools for s in slots.slots.values()):
            return Decision({"applied": False, "message": "Te falta la herramienta apropiada."}, {})
        rate = min(100, recipe["success_rate"] + max(0, level - recipe["required"]) // 2)
        success = sample < rate / 100
        try:
            # La bolsa debe admitir la fabricación completa incluso al fallar.
            capacity = SlotPlan(slots.fields(), slots.capacity, slots.max_stack)
            consume_materials(capacity, recipe["materials"], quantity)
            capacity.give(recipe["item_id"], quantity)
            if success:
                slots = capacity
            else:
                half = [
                    {**m, "quantity": math.ceil(m["quantity"] * quantity / 2)}
                    for m in recipe["materials"]
                ]
                consume_materials(slots, half, 1)
        except ValueError as error:
            return Decision({"applied": False, "message": str(error)}, {})
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "successful": success,
                    "quantity": quantity if success else 0,
                    "item_id": recipe["item_id"],
                    "message": f"Has fabricado {quantity} {recipe['name']}."
                    if success
                    else "La fabricación falló y perdiste la mitad de los materiales.",
                },
                {inv_key: slots.fields()},
            ),
            snapshot,
            user_id,
            ((skill, success),),
        )

    watched = (
        *training_resources(user_id),
        Resource(inv_key, "hash"),
        Resource(pos_key, "hash"),
        Resource(CRAFTING_KEY, "string"),
    )
    return await transact(
        player.redis.redis,
        watched,
        identity or operation_id(),
        {"craft": user_id, "recipe": recipe_id, "quantity": quantity},
        decide,
    )
