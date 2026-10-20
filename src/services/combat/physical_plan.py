"""Golpes físicos: coste, daño y entrenamiento compartiendo el mismo snapshot."""

import json
import math
import random
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from src.combat.combat_critical_calculator import CriticalCalculator
from src.models.skill_data_loader import SKILL_RULES_KEY
from src.models.skills import skill_progress
from src.services.combat.barriers import absorb_damage
from src.services.combat.clan_policy import ClanCombat
from src.services.combat.pvp_policy import PvpPolicy
from src.services.npc.guard_ai import GUARD_RADIUS, guard_enemy
from src.services.player.lifecycle import hp_changes
from src.services.player.lifetime_stats import kill_changes
from src.services.skill_training import TrainingEvent, trained_decision, training_resources
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

ASSASSIN_CLASS = 4
BARD_CLASS = 6
BACKSTAB_OTHER_MINIMUM = 10
AMMUNITION_TYPE = 32


if TYPE_CHECKING:
    from collections.abc import Callable

    from redis.asyncio import Redis

    from src.models.item_catalog import ItemCatalog

MAX_SKILL = 100
ATTACK_STAMINA = 2
MAX_PHYSICAL_RANGE = 8


def levels(snapshot: Snapshot, user: int) -> dict[str, int]:
    """Obtiene niveles canónicos sin usar la XP acumulada como poder de combate.

    Returns:
        Niveles de todas las habilidades, incluidas las extensiones propias.
    """
    return {
        p.definition.key: p.level
        for p in skill_progress(cast("dict[str, str]", snapshot[RedisKeys.player_skills(user)]))
        if p.definition.key is not None
    }


def equipped(snapshot: Snapshot, user: int, slot: str, catalog: ItemCatalog) -> dict[str, object]:
    """Resuelve el objeto equipado desde inventario y equipo observados juntos.

    Returns:
        Datos del objeto real, o vacío para un slot sin equipar.
    """
    gear = cast("dict[str, str]", snapshot[RedisKeys.player_equipment(user)])
    bag = cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)])
    value = bag.get(f"slot_{gear.get(slot, '0')}", "")
    return catalog.get_item_data(int(value.split(":")[0])) or {} if value else {}


def backstab_chance(skill: int, player_class: int) -> int:
    """Aplica las curvas de apuñalar del servidor AO 0.13.3.

    Returns:
        Éxitos de una tirada de cero a cien.
    """
    if player_class == ASSASSIN_CLASS:
        return math.floor(((0.00003 * skill - 0.002) * skill + 0.098) * skill + 4.25)
    if player_class in {2, 9, 12}:
        return math.floor(((0.000003 * skill + 0.0006) * skill + 0.0107) * skill + 4.93)
    if player_class == BARD_CLASS:
        return math.floor(((0.000002 * skill + 0.0002) * skill + 0.032) * skill + 4.81)
    return math.floor(0.0361 * skill + 4.39)


def effective_attribute(snapshot: Snapshot, user: int, name: str, now: float) -> int:
    """Conserva atributos y buffs propios sin confundirlos con las habilidades 21/22.

    Returns:
        Atributo actual, respetando los límites previos de los modificadores.
    """
    attrs = cast("dict[str, str]", snapshot[RedisKeys.player_stats(user)])
    base = int(attrs.get(name, 10))
    modifier = int(attrs.get(f"{name}_modifier_value", 0))
    if float(attrs.get(f"{name}_modifier_until", 0)) <= now or modifier == 0:
        return base
    return max(1, min(50, base * 2, base + modifier))


def defense(
    snapshot: Snapshot,
    user: int,
    catalog: ItemCatalog,
    damage: int,
    hit_roll: float,
    shield_roll: float,
    rules: dict[str, Any],
    *,
    accuracy: float = 1.0,
) -> tuple[int, bool, bool, tuple[TrainingEvent, ...]]:
    """Separa evasión, bloqueo y mitigación; sólo el escudo equipado entrena defensa.

    Returns:
        Daño, esquive, bloqueo e intentos naturales del defensor.
    """
    skills = levels(snapshot, user)
    stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(user)])
    agility = effective_attribute(snapshot, user, "agility", time.time())
    dodge = min(
        0.60,
        CriticalCalculator().calculate_dodge_chance(agility)
        + skills["tacticas"] / 400
        + skills["agilidad"] / MAX_SKILL * float(rules.get("agility_max_evasion", 0.10)),
    )
    dodged = hit_roll < 1 - accuracy * (1 - dodge)
    shield = equipped(snapshot, user, "shield", catalog)
    if int(stats.get("class_id", 0)) not in rules.get("playable_classes", list(range(1, 13))):
        shield = {}
    blocked = bool(shield) and not dodged and shield_roll < skills["defensa"] / 300
    armor = equipped(snapshot, user, "armor", catalog)
    reduction = min(
        0.5, 0.1 + (int(str(armor.get("MinDef", 0))) + int(str(armor.get("MaxDef", 0)))) / 200
    )
    robustness = (
        skills["robustez"] / MAX_SKILL * float(rules.get("robustness_max_mitigation", 0.10))
    )
    final = 0 if dodged or blocked else max(1, round(damage * (1 - reduction) * (1 - robustness)))
    events: tuple[TrainingEvent, ...] = (("tacticas", dodged),)
    if shield and not dodged:
        events += (("defensa", blocked),)
    return final, dodged, blocked, events


@dataclass(frozen=True)
class PhysicalRequest:
    """Intención estable para un ataque cuerpo a cuerpo o con proyectiles."""

    user_id: int
    target_player: int = 0
    target_npc: str = ""
    ranged: bool = False


class PhysicalPlan:
    """Revalida equipo, blancos, posiciones, vida y seguro antes de cualquier gasto."""

    def __init__(
        self, request: PhysicalRequest, catalog: ItemCatalog, capacity: int, stack: int
    ) -> None:
        """Congela el azar antes de los reintentos de WATCH."""
        self.request, self.catalog = request, catalog
        self.capacity, self.stack = capacity, stack
        self.roll, self.shield_roll, self.stab_roll, self.damage_roll = (
            random.random() for _ in range(4)
        )
        self.critical_roll = random.random()
        self.now = time.time()
        self.world_guard: Callable[[Snapshot], bool] | None = None
        self.clan_policy: ClanCombat | None = None
        users = {request.user_id, request.target_player} - {0}
        resources = [
            r
            for user in sorted(users)
            for r in (
                *training_resources(user),
                Resource(RedisKeys.player_position(user), "hash"),
                Resource(RedisKeys.player_equipment(user), "hash"),
                Resource(RedisKeys.player_inventory(user), "hash"),
            )
        ]
        if request.target_npc:
            resources.append(Resource(RedisKeys.npc_instance(request.target_npc), "hash"))
        self.resources = tuple({r.key: r for r in resources}.values())

    def decide(self, snapshot: Snapshot) -> Decision:  # ruff: ignore[too-many-locals, too-many-statements] - un único commit de combate
        """Confirma una acción válida con daño, munición, stamina y entrenamiento.

        Returns:
            Resultado reproducible; los rechazos no consumen recursos ni entrenan.
        """
        request = self.request
        user = request.user_id
        source_key, pos_key = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
        source, position = (
            cast("dict[str, str]", snapshot[source_key]),
            cast("dict[str, str]", snapshot[pos_key]),
        )
        target_key = (
            RedisKeys.player_user_stats(request.target_player)
            if request.target_player
            else RedisKeys.npc_instance(request.target_npc)
        )
        target = cast("dict[str, str]", snapshot[target_key])
        target_position = (
            cast("dict[str, str]", snapshot[RedisKeys.player_position(request.target_player)])
            if request.target_player
            else {
                "map": target.get("map_id", "0"),
                "x": target.get("x", "0"),
                "y": target.get("y", "0"),
            }
        )
        distance = max(
            abs(int(position.get("x", 0)) - int(target_position.get("x", 0))),
            abs(int(position.get("y", 0)) - int(target_position.get("y", 0))),
        )
        rejection = ""
        if request.target_player:
            rejection = (
                PvpPolicy.configured().rejection(
                    user,
                    request.target_player,
                    position,
                    target_position,
                    source,
                    target,
                    self.clan_policy.relationship(snapshot) if self.clan_policy else "neutral",
                )
                or ""
            )
        elif str(target.get("is_attackable", "false")).lower() not in {"1", "true"}:
            rejection = "No puedes atacar a ese NPC."
        if rejection:
            return Decision({"applied": False, "message": rejection}, {})
        invalid_state = (
            not target
            or int(source.get("min_hp", 0)) <= 0
            or int(target.get("min_hp", target.get("hp", 0))) <= 0
        )
        invalid_position = (
            position.get("map") != target_position.get("map")
            or distance < 1
            or distance > (MAX_PHYSICAL_RANGE if request.ranged else 1)
        )
        invalid_world = self.world_guard is not None and not self.world_guard(snapshot)
        if (
            invalid_state
            or invalid_position
            or float(source.get("paralyzed_until", 0)) > self.now
            or int(source.get("min_sta", 0)) < ATTACK_STAMINA
            or invalid_world
        ):
            return Decision(
                {
                    "applied": False,
                    "message": "Objetivo fuera de alcance o estado de ataque inválido.",
                },
                {},
            )
        weapon = equipped(snapshot, user, "weapon", self.catalog)
        bow = bool(weapon.get("Proyectil"))
        if bow != request.ranged:
            return Decision(
                {"applied": False, "message": "Usa el cursor de proyectiles con un arco equipado."},
                {},
            )
        skill = "proyectiles" if bow else "armas" if weapon else "wrestling"
        skills = levels(snapshot, user)
        power = int(str(weapon.get("MinHit", 2))) + self.damage_roll * (
            int(str(weapon.get("MaxHit", 2))) - int(str(weapon.get("MinHit", 2)))
        )
        strength = effective_attribute(snapshot, user, "strength", self.now)
        agility = effective_attribute(snapshot, user, "agility", self.now)
        amount = max(1, round(strength / 2 + power + skills[skill] / 10))
        critical_calculator = CriticalCalculator()
        critical = self.critical_roll < critical_calculator.calculate_critical_chance(agility)
        if critical:
            amount = critical_calculator.apply_critical_damage(amount)
        writes: dict[str, str | dict[str, str] | set[str]] = {
            source_key: {
                "min_sta": str(int(source["min_sta"]) - ATTACK_STAMINA),
                "hidden_until": "0",
                "meditating": "0",
            }
        }
        projectile_asset = 0
        if bow:
            slots = SlotPlan(
                cast("dict[str, str]", snapshot[RedisKeys.player_inventory(user)]),
                self.capacity,
                self.stack,
            )
            ammo = next(
                (
                    (i, s)
                    for i, s in slots.slots.items()
                    if (self.catalog.get_item_data(s.item_id) or {}).get("ObjType")
                    == AMMUNITION_TYPE
                ),
                None,
            )
            if ammo is None:
                return Decision(
                    {"applied": False, "message": "No tienes munición para el arco."}, {}
                )
            slots.take(ammo[0], ammo[1].item_id, 1)
            projectile_asset = self.catalog.get_grh_index(ammo[1].item_id) or 0
            writes[RedisKeys.player_inventory(user)] = slots.fields()
        rules = json.loads(str(snapshot.get(SKILL_RULES_KEY) or "{}"))
        blocked = False
        defender_events: tuple[TrainingEvent, ...] = ()
        if request.target_player:
            amount, dodged, blocked, defender_events = defense(
                snapshot,
                request.target_player,
                self.catalog,
                amount,
                self.roll,
                self.shield_roll,
                rules,
                accuracy=max(0.10, min(0.95, 0.60 + skills[skill] / 250)),
            )
        else:
            # La habilidad de ataque reduce los fallos frente al nivel del NPC.
            chance = max(
                0.10, min(0.95, 0.60 + skills[skill] / 250 - int(target.get("level", 1)) / 500)
            )
            dodged = self.roll >= chance
            if dodged:
                amount = 0
        successful = not dodged and not blocked
        events: tuple[TrainingEvent, ...] = ((skill, successful),)
        player_class = int(source.get("class_id", 0))
        stab_eligible = (
            successful
            and bool(weapon.get("Apuñala"))
            and (player_class == ASSASSIN_CLASS or skills["apunalar"] >= BACKSTAB_OTHER_MINIMUM)
        )
        stabbed = stab_eligible and self.stab_roll * 101 < backstab_chance(
            skills["apunalar"], player_class
        )
        if stab_eligible:
            events += (("apunalar", stabbed),)
        if stabbed:
            amount += (
                round(amount * (1.4 if player_class == ASSASSIN_CLASS else 1.5))
                if request.target_player
                else amount * 2
            )
        amount, barrier = (
            absorb_damage(target, amount, "physical", self.now)
            if request.target_player
            else (amount, {})
        )
        hp = max(0, int(target.get("min_hp", target.get("hp", 0))) - amount)
        if hp == 0:
            cast("dict[str, str]", writes[source_key]).update(
                kill_changes(source, target, player=bool(request.target_player))
            )
        writes[target_key] = (
            {**barrier, **hp_changes(target, target_position, hp, f"physical:{user}:{self.now}")}
            if request.target_player
            else {"hp": str(hp)}
        )
        result = {
            "applied": True,
            "damage": amount,
            "projectile_asset": projectile_asset,
            "critical": successful and (critical or stabbed),
            "backstab": stabbed,
            "dodged": dodged,
            "blocked": blocked,
            "npc_died": hp <= 0 and not request.target_player,
            "player_died": hp <= 0 and bool(request.target_player),
            "new_hp": hp,
            "life_id": int(target.get("life_id", 0)),
            "target_x": int(target_position.get("x", 0)),
            "target_y": int(target_position.get("y", 0)),
        }
        decision = trained_decision(Decision(result, writes), snapshot, user, events)
        return (
            trained_decision(decision, snapshot, request.target_player, defender_events)
            if request.target_player
            else decision
        )


async def commit_physical(redis: Redis, plan: PhysicalPlan, identity: str) -> dict[str, Any]:
    """Ejecuta el plan y recupera el mismo resultado al reintentar.

    Returns:
        Recibo del golpe validado sobre Redis.
    """
    request = plan.request
    if request.target_player and plan.clan_policy is None:
        plan.clan_policy = await ClanCombat.prepare(redis, request.user_id, request.target_player)
        plan.resources = tuple(
            {r.key: r for r in (*plan.resources, *plan.clan_policy.resources)}.values()
        )
    return await transact(
        redis,
        plan.resources,
        identity,
        {
            "physical": request.user_id,
            "player": request.target_player,
            "npc": request.target_npc,
            "ranged": request.ranged,
        },
        plan.decide,
    )


async def defend_npc(
    redis: Redis, user: int, npc_id: str, catalog: ItemCatalog, damage: int, identity: str
) -> dict[str, Any]:
    """Confirma evasión, bloqueo, robustez y daño de NPC junto con sus entrenamientos.

    Returns:
        HP y generación vital del golpe; un blanco inválido no recibe daño ni XP.
    """
    hit_roll, shield_roll = random.random(), random.random()
    now = time.time()
    stats_key, position_key = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
    npc_key = RedisKeys.npc_instance(npc_id)
    resources = (
        *training_resources(user),
        Resource(position_key, "hash"),
        Resource(RedisKeys.player_inventory(user), "hash"),
        Resource(RedisKeys.player_equipment(user), "hash"),
        Resource(npc_key, "hash"),
    )

    def decide(snapshot: Snapshot) -> Decision:
        stats, position, npc = (
            cast("dict[str, str]", snapshot[k]) for k in (stats_key, position_key, npc_key)
        )
        hp = int(stats.get("min_hp", 0))
        base = {
            "applied": False,
            "damage": 0,
            "new_hp": hp,
            "player_died": hp <= 0,
            "life_id": int(stats.get("life_id", 0)),
        }
        if (
            hp <= 0
            or not npc
            or int(npc.get("hp", 0)) <= 0
            or npc.get("map_id") != position.get("map")
        ):
            return Decision(base, {})
        if npc.get("role") == "guard" and (
            not guard_enemy(stats, npc.get("guard_faction", "neutral"))
            or abs(int(position.get("x", 0)) - int(npc.get("home_x", npc.get("x", 0))))
            + abs(int(position.get("y", 0)) - int(npc.get("home_y", npc.get("y", 0))))
            > GUARD_RADIUS
            or float(npc.get("paralyzed_until", 0)) > now
        ):
            return Decision(base, {})
        if (
            max(
                abs(int(position.get("x", 0)) - int(npc.get("x", 0))),
                abs(int(position.get("y", 0)) - int(npc.get("y", 0))),
            )
            > 1
        ):
            return Decision(base, {})
        if now - float(npc.get("last_attack_time", 0)) < float(npc.get("attack_cooldown", 3)):
            return Decision(base, {})
        rules = json.loads(str(snapshot.get(SKILL_RULES_KEY) or "{}"))
        actual, dodged, blocked, events = defense(
            snapshot, user, catalog, damage, hit_roll, shield_roll, rules
        )
        actual, barrier = absorb_damage(stats, actual, "physical", now)
        new_hp = max(0, hp - actual)
        return trained_decision(
            Decision(
                {
                    **base,
                    "applied": True,
                    "damage": actual,
                    "dodged": dodged,
                    "blocked": blocked,
                    "new_hp": new_hp,
                    "player_died": new_hp <= 0,
                },
                {
                    stats_key: {**barrier, **hp_changes(stats, position, new_hp, identity)},
                    npc_key: {"last_attack_time": str(now)},
                },
            ),
            snapshot,
            user,
            events,
        )

    return await transact(
        redis, resources, identity, {"defend": user, "npc": npc_id, "damage": damage}, decide
    )
