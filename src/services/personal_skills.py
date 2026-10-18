"""Acciones de robar, ocultarse, supervivencia y domar confirmadas en Redis."""

import json
import random
import time
from typing import TYPE_CHECKING, Any, cast

from src.constants.gameplay import MAX_PETS
from src.models.item_constants import MAX_PLAYER_GOLD
from src.models.skill_data_loader import SKILL_RULES_KEY
from src.services.combat.physical_plan import levels
from src.services.combat.pvp_policy import PvpPolicy
from src.services.crafting import consume_materials
from src.services.meditation import MEDITATION_LUCK
from src.services.skill_training import trained_decision, training_resources
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

MAX_SKILL = 100
THIEF_CLASS = 5
ITEM_THEFT_CHANCE = 0.48
FIRE_NOVICE_LIMIT = 6
FIRE_EXPERT_LIMIT = 34


if TYPE_CHECKING:
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

TAME_CHANCE = 0.20
THEFT_STAMINA = 15
GOLD_LIMIT = MAX_PLAYER_GOLD
SAME_PET_LIMIT = 2


def player_action_resources(user: int) -> tuple[Resource, ...]:
    """Incluye equipo e inventario para evitar actuar con objetos que ya cambiaron.

    Returns:
        Recursos del actor para una operación completa.
    """
    return (
        *training_resources(user),
        Resource(RedisKeys.player_position(user), "hash"),
        Resource(RedisKeys.player_inventory(user), "hash"),
        Resource(RedisKeys.player_equipment(user), "hash"),
    )


def valid_actor(
    snapshot: Snapshot, user: int, map_id: int, x: int, y: int, distance: int = 1
) -> bool:
    """Valida vida, posición y distancia desde el snapshot observado.

    Returns:
        Si el actor puede intentar la acción en la casilla indicada.
    """
    stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user)])
    pos = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
    return (
        int(stats.get("min_hp", 0)) > 0
        and int(pos.get("map", 0)) == map_id
        and 1 <= x <= MAX_SKILL
        and 1 <= y <= MAX_SKILL
        and max(abs(int(pos.get("x", 0)) - x), abs(int(pos.get("y", 0)) - y)) <= distance
    )


async def hide(player: PlayerRepository, user: int, identity: str) -> dict[str, Any]:
    """Oculta con la curva clásica; repetir mientras está oculto sólo cancela el estado.

    Returns:
        Éxito o fallo válido, con duración persistida y XP conjunta.
    """
    sample, now = random.random(), time.time()
    key = RedisKeys.player_user_stats(user)

    def decide(snapshot: Snapshot) -> Decision:
        stats = cast("dict[str, str]", snapshot[key])
        if int(stats.get("min_hp", 0)) <= 0:
            return Decision(
                {"applied": False, "message": "No puedes ocultarte estando muerto."}, {}
            )
        if float(stats.get("hidden_until", 0)) > now:
            return Decision(
                {"applied": True, "message": "Has dejado de ocultarte."},
                {key: {"hidden_until": "0"}},
            )
        level = levels(snapshot, user)["ocultarse"]
        chance = ((0.000002 * level - 0.0002) * level + 0.0064) * level + 0.1124
        success = sample < min(1.0, chance)
        rules = json.loads(str(snapshot.get(SKILL_RULES_KEY) or "{}"))
        duration = max(1.0, float(rules.get("hide_max_seconds", 60)) * (level + 10) / 110)
        duration *= float(
            rules.get("hiding_duration_modifiers", {}).get(stats.get("class_id", "0"), 1.0)
        )
        changes = {"hidden_until": str(now + duration if success else 0), "meditating": "0"}
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "successful": success,
                    "message": "Te has escondido entre las sombras."
                    if success
                    else "No has logrado esconderte.",
                },
                {key: changes},
            ),
            snapshot,
            user,
            (("ocultarse", success),),
        )

    return await transact(
        player.redis.redis, player_action_resources(user), identity, {"hide": user}, decide
    )


async def steal(
    player: PlayerRepository,
    inventory: InventoryRepository,
    catalog: ItemCatalog,
    user: int,
    target: int,
    identity: str,
) -> dict[str, Any]:
    """Roba oro con cualquier clase u objetos sin equipar con Ladrón.

    Returns:
        Transferencia conjunta y entrenamiento, o rechazo sin cobro.
    """
    sample, choice_roll = random.random(), random.random()
    source_key, target_key = RedisKeys.player_user_stats(user), RedisKeys.player_user_stats(target)
    source_bag, target_bag = RedisKeys.player_inventory(user), RedisKeys.player_inventory(target)
    resources = tuple(
        {r.key: r for uid in sorted({user, target}) for r in player_action_resources(uid)}.values()
    )

    def decide(snapshot: Snapshot) -> Decision:  # noqa: PLR0914 - dos inventarios y saldos en un commit
        stats, victim = (
            cast("dict[str, str]", snapshot[source_key]),
            cast("dict[str, str]", snapshot[target_key]),
        )
        pos, target_pos = (
            cast("dict[str, str]", snapshot[RedisKeys.player_position(uid)])
            for uid in (user, target)
        )
        error = PvpPolicy.configured().rejection(user, target, pos, target_pos, stats, victim)
        if error or not valid_actor(
            snapshot,
            user,
            int(target_pos.get("map", 0)),
            int(target_pos.get("x", 0)),
            int(target_pos.get("y", 0)),
        ):
            return Decision(
                {"applied": False, "message": error or "Debes estar junto a la víctima."}, {}
            )
        if int(stats.get("min_sta", 0)) < THEFT_STAMINA:
            return Decision(
                {"applied": False, "message": "Necesitas 15 de energía para robar."}, {}
            )
        bag, other = (
            SlotPlan(
                cast("dict[str, str]", snapshot[k]),
                inventory.MAX_SLOTS,
                inventory.stacking.max_stack,
            )
            for k in (source_bag, target_bag)
        )
        gear = cast("dict[str, str]", snapshot[RedisKeys.player_equipment(target)])
        equipped_slots = {int(value) for value in gear.values() if value.isdecimal()}
        loot = [
            (slot, item)
            for slot, item in other.slots.items()
            if slot not in equipped_slots
            and not (catalog.get_item_data(item.item_id) or {}).get("Nosecae")
            and not (catalog.get_item_data(item.item_id) or {}).get("Crucial")
        ]
        thief = int(stats.get("class_id", 0)) == THIEF_CLASS
        if int(victim.get("gold", 0)) <= 0 and not (thief and loot):
            return Decision(
                {"applied": False, "message": "La víctima no tiene recursos robables."}, {}
            )
        level = levels(snapshot, user)["robar"]
        band = min(10, max(0, (level - 1) // 10)) if level < MAX_SKILL else 10
        success = sample < 2 / MEDITATION_LUCK[band]
        writes: dict[str, str | dict[str, str] | set[str]] = {
            source_key: {"min_sta": str(int(stats["min_sta"]) - THEFT_STAMINA), "hidden_until": "0"}
        }
        stolen_gold, item_id = 0, 0
        if (
            success
            and thief
            and loot
            and (choice_roll < ITEM_THEFT_CHANCE or int(victim.get("gold", 0)) <= 0)
        ):
            slot, item = loot[min(len(loot) - 1, int(choice_roll * len(loot)))]
            try:
                bag.give(item.item_id, 1)
                other.take(slot, item.item_id, 1)
            except ValueError as error:
                return Decision({"applied": False, "message": str(error)}, {})
            item_id = item.item_id
            writes.update({source_bag: bag.fields(), target_bag: other.fields()})
        elif success:
            amount = (
                max(1, int(stats.get("level", 1)) * (25 + int(choice_roll * 26)))
                if thief
                else 1 + int(choice_roll * 100)
            )
            stolen_gold = min(
                amount, int(victim.get("gold", 0)), GOLD_LIMIT - int(stats.get("gold", 0))
            )
            if stolen_gold <= 0:
                return Decision({"applied": False, "message": "No puedes recibir más oro."}, {})
            cast("dict[str, str]", writes[source_key])["gold"] = str(
                int(stats.get("gold", 0)) + stolen_gold
            )
            writes[target_key] = {"gold": str(int(victim.get("gold", 0)) - stolen_gold)}
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "successful": success,
                    "gold": stolen_gold,
                    "item_id": item_id,
                    "message": f"Has robado {stolen_gold} monedas."
                    if stolen_gold
                    else "Has robado un objeto."
                    if item_id
                    else "No has logrado robar nada.",
                },
                writes,
            ),
            snapshot,
            user,
            (("robar", success),),
        )

    return await transact(
        player.redis.redis, resources, identity, {"steal": user, "target": target}, decide
    )


async def survival(
    player: PlayerRepository,
    inventory: InventoryRepository,
    terrain: MapResourcesService,
    user: int,
    map_id: int,
    x: int,
    y: int,
    identity: str,
    *,
    npc_id: str = "",
) -> dict[str, Any]:
    """Inspecciona una criatura o enciende una fogata con tres leños del inventario.

    Returns:
        Información o fogata persistida con vencimiento, junto con el progreso.
    """
    now, sample = time.time(), random.random()
    fire_key = f"world:campfire:{map_id}:{x}:{y}"
    npc_key = RedisKeys.npc_instance(npc_id)
    resources = (
        *player_action_resources(user),
        Resource(fire_key, "hash", ttl_seconds=120),
        Resource(npc_key, "hash"),
    )

    def decide(snapshot: Snapshot) -> Decision:
        if not valid_actor(snapshot, user, map_id, x, y, distance=2):
            return Decision(
                {"applied": False, "message": "Debes estar vivo y cerca del objetivo."}, {}
            )
        level = levels(snapshot, user)["supervivencia"]
        writes: dict[str, str | dict[str, str] | set[str]] = {}
        if npc_id:
            npc = cast("dict[str, str]", snapshot[npc_key])
            if not npc or (
                int(npc.get("map_id", 0)),
                int(npc.get("x", 0)),
                int(npc.get("y", 0)),
            ) != (map_id, x, y):
                return Decision({"applied": False, "message": "La criatura se ha movido."}, {})
            success = sample < (level + 10) / 110
            message = (
                f"{npc.get('name', 'Criatura')}: {npc.get('hp', 0)}/{npc.get('max_hp', 0)} de vida."
                if success
                else "No logras reconocer el estado de la criatura."
            )
        else:
            if (
                terrain.is_blocked(map_id, x, y)
                or terrain.has_water(map_id, x, y)
                or snapshot[fire_key]
            ):
                return Decision(
                    {"applied": False, "message": "No puedes encender una fogata ahí."}, {}
                )
            inv_key = RedisKeys.player_inventory(user)
            slots = SlotPlan(
                cast("dict[str, str]", snapshot[inv_key]),
                inventory.MAX_SLOTS,
                inventory.stacking.max_stack,
            )
            try:
                consume_materials(slots, [{"item_id": 58, "quantity": 3}], 1)
            except ValueError as error:
                return Decision({"applied": False, "message": str(error)}, {})
            success = sample < 1 / (
                3 if level < FIRE_NOVICE_LIMIT else 2 if level <= FIRE_EXPERT_LIMIT else 1
            )
            if success:
                writes.update(
                    {
                        inv_key: slots.fields(),
                        fire_key: {
                            "owner": str(user),
                            "until": str(now + 120),
                            "map": str(map_id),
                            "x": str(x),
                            "y": str(y),
                        },
                    }
                )
            message = (
                "Has encendido una fogata durante dos minutos."
                if success
                else "No has logrado encender la fogata."
            )
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "successful": success,
                    "fire": not npc_id and success,
                    "message": message,
                },
                writes,
            ),
            snapshot,
            user,
            (("supervivencia", success),),
        )

    return await transact(
        player.redis.redis,
        resources,
        identity,
        {"survival": user, "map": map_id, "x": x, "y": y, "npc": npc_id},
        decide,
    )


async def tame(
    player: PlayerRepository, user: int, npc_id: str, pet_ids: list[str], identity: str
) -> dict[str, Any]:
    """Doma por Carisma por Domar, con límite global y dos criaturas de cada tipo.

    Returns:
        Propietario permanente de la criatura y entrenamiento del intento.
    """
    sample, now = random.random(), time.time()
    npc_key, pets_key = RedisKeys.npc_instance(npc_id), f"player:{user}:pets"
    known = sorted({*pet_ids, npc_id})
    resources = (
        *player_action_resources(user),
        Resource(pets_key, "set"),
        *(Resource(RedisKeys.npc_instance(pet), "hash") for pet in known),
    )

    def decide(snapshot: Snapshot) -> Decision:
        npc = cast("dict[str, str]", snapshot[npc_key])
        if not npc or not valid_actor(
            snapshot, user, int(npc.get("map_id", 0)), int(npc.get("x", 0)), int(npc.get("y", 0))
        ):
            return Decision(
                {"applied": False, "message": "Debes estar vivo y junto a la criatura."}, {}
            )
        rules = json.loads(str(snapshot.get(SKILL_RULES_KEY) or "{}"))
        stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user)])
        if int(stats.get("class_id", 0)) not in rules.get("playable_classes", list(range(1, 13))):
            return Decision({"applied": False, "message": "Clase de personaje inválida."}, {})
        members = set(cast("set[str]", snapshot[pets_key]))
        if members - set(known):
            return Decision(
                {"applied": False, "message": "Tus mascotas cambiaron; vuelve a intentarlo."}, {}
            )
        pets = [cast("dict[str, str]", snapshot[RedisKeys.npc_instance(pet)]) for pet in known]
        pets = [
            p
            for p in pets
            if int(p.get("summoned_by_user_id", 0)) == user
            and int(p.get("hp", 0)) > 0
            and (
                p.get("is_tamed", "False").lower() == "true"
                or float(p.get("summoned_until", 0)) > now
            )
        ]
        if (
            int(npc.get("domable", 0)) <= 0
            or int(npc.get("hp", 0)) <= 0
            or int(npc.get("summoned_by_user_id", 0))
        ):
            return Decision(
                {"applied": False, "message": "La criatura no es domable o ya tiene dueño."}, {}
            )
        if (
            len(pets) >= MAX_PETS
            or sum(p.get("npc_id") == npc.get("npc_id") for p in pets) >= SAME_PET_LIMIT
        ):
            return Decision(
                {
                    "applied": False,
                    "message": "Alcanzaste el límite de mascotas o de criaturas del mismo tipo.",
                },
                {},
            )
        attributes = cast("dict[str, str]", snapshot[RedisKeys.player_stats(user)])
        power = int(attributes.get("charisma", 10)) * levels(snapshot, user)["domar"]
        success = power >= int(npc["domable"]) and sample < TAME_CHANCE
        writes: dict[str, str | dict[str, str] | set[str]] = {}
        if success:
            writes[npc_key] = {
                "summoned_by_user_id": str(user),
                "summoned_until": "0",
                "is_tamed": "True",
                "is_hostile": "False",
                "movement_type": "static",
                "respawn_time": "0",
            }
            writes[pets_key] = members | {npc_id}
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "successful": success,
                    "message": "La criatura te ha aceptado como su amo."
                    if success
                    else "No has logrado domar la criatura.",
                },
                writes,
            ),
            snapshot,
            user,
            (("domar", success),),
        )

    return await transact(
        player.redis.redis, resources, identity, {"tame": user, "npc": npc_id}, decide
    )
