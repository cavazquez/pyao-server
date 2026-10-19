"""Plan puro de magia: valida snapshot y confirma coste y efecto con un recibo."""

import random
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, cast

from src.models.skills import skill_progress
from src.services.combat.pvp_policy import PvpPolicy, is_hostile
from src.services.player.lifecycle import hp_changes, revive_changes
from src.services.skill_training import trained_decision, training_resources
from src.utils.durability import require_durable
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from collections.abc import Callable

    from redis.asyncio import Redis

NPC_ONLY_TARGET = 2
MAX_RANGE = 10
MAX_COORD = 100
MAX_SLOT = 35
ATTRIBUTE_MODIFIER_MIN = 2
ATTRIBUTE_MODIFIER_MAX = 5
DRAIN_SPELL = 45
MORPH_SPELL = 42
HUNGER_SPELLS = (12, 13)


@dataclass(frozen=True)
class CastRequest:
    """Una intención congelada; su identidad se conserva al resolver un ACK incierto."""

    user_id: int
    spell_id: int
    x: int
    y: int
    slot: int = 0
    target_player: int = 0
    target_npc: str = ""
    target_username: str = ""


class SpellPlan:
    """Toda decisión se repite sobre los recursos observados por WATCH."""

    def __init__(self, request: CastRequest, spell: dict[str, Any], policy: PvpPolicy) -> None:
        """Congela azar y política antes de los reintentos, sin cobrar recursos."""
        self.staff_items: frozenset[int] = frozenset()
        self.world_guard: Callable[[], bool] | None = None
        self.event_id = ""
        self.request = request
        self.spell = spell
        self.policy = policy
        self.now = time.time()
        self.base_amount = random.randint(
            int(spell.get("min_damage", 0)), int(spell.get("max_damage", 0))
        )
        self.modifier = random.randint(ATTRIBUTE_MODIFIER_MIN, ATTRIBUTE_MODIFIER_MAX)
        users = {request.user_id, request.target_player} - {0}
        keys = {
            factory(user)
            for user in users
            for factory in (
                RedisKeys.player_user_stats,
                RedisKeys.player_position,
                RedisKeys.player_stats,
                RedisKeys.player_hunger_thirst,
            )
        }
        keys.update(
            (
                RedisKeys.player_spellbook(request.user_id),
                RedisKeys.player_skills(request.user_id),
                RedisKeys.player_equipment(request.user_id),
                RedisKeys.player_inventory(request.user_id),
            )
        )
        if request.target_npc:
            keys.add(RedisKeys.npc_instance(request.target_npc))
        if request.target_username:
            keys.add(RedisKeys.account_data(request.target_username))
        self.resources = tuple(
            {
                resource.key: resource
                for resource in (
                    *(Resource(key, "hash") for key in sorted(keys)),
                    *training_resources(request.user_id),
                )
            }.values()
        )

    def decide(self, snapshot: Snapshot) -> Decision:  # noqa: PLR0914, PLR0915 - plan puro de un commit
        """Rechaza antes del coste; un EXEC confirma maná, stamina y todos los efectos.

        Returns:
            Resultado estable y campos exactos de recursos confirmados conjuntamente.
        """
        values = {key: cast("dict[str, str]", value) for key, value in snapshot.items()}
        request = self.request
        if self.world_guard is not None and not self.world_guard():
            return Decision({"applied": False, "message": "El objetivo o la sesión cambió."}, {})
        source_key = RedisKeys.player_user_stats(request.user_id)
        source = values[source_key]
        position = values[RedisKeys.player_position(request.user_id)]
        book = values[RedisKeys.player_spellbook(request.user_id)]
        error = self._validate_caster(values, source, position, book)
        if error:
            return Decision({"applied": False, "message": error}, {})
        target_key = (
            RedisKeys.player_user_stats(request.target_player)
            if request.target_player
            else RedisKeys.npc_instance(request.target_npc)
        )
        target = values.get(target_key, {})
        target_position = (
            values[RedisKeys.player_position(request.target_player)]
            if request.target_player
            else {
                "map": target.get("map_id", "0"),
                "x": target.get("x", "0"),
                "y": target.get("y", "0"),
            }
        )
        error = self._validate_target(source, position, target, target_position)
        if error:
            return Decision({"applied": False, "message": error}, {})
        writes: dict[str, str | dict[str, str]] = {}
        target_changes: dict[str, str] = {}
        source_changes = {
            "hidden_until": "0",
            "meditating": "0",
            "min_mana": str(int(source.get("min_mana", 0)) - int(self.spell.get("mana_cost", 0))),
            "min_sta": str(int(source.get("min_sta", 0)) - int(self.spell.get("stamina_cost", 3))),
        }
        attributes = values[RedisKeys.player_stats(request.user_id)]
        amount = (
            self.base_amount + self.base_amount * int(attributes.get("intelligence", 10)) // 100
        )
        hp_field = "min_hp" if request.target_player else "hp"
        hp = int(target.get(hp_field, target.get("hp", 0)))
        maximum = int(target.get("max_hp", 100))
        if self.spell.get("revives"):
            # La generación impide resucitar mientras la liquidación de muerte está pendiente.
            if target.get("death_state") != "complete":
                return Decision(
                    {"applied": False, "message": "La muerte todavía no está liquidada."}, {}
                )
            target_changes.update(revive_changes(target))
        elif self.spell.get("heals_hp"):
            target_changes[hp_field] = str(min(maximum, hp + amount))
        elif amount > 0:
            target_changes[hp_field] = str(max(0, hp - amount))
        if request.target_player and "hp" in target and hp_field in target_changes:
            target_changes["hp"] = target_changes[hp_field]
        if request.target_player and int(target_changes.get("min_hp", hp)) <= 0:
            target_changes.update(
                hp_changes(
                    target,
                    target_position,
                    0,
                    f"cast:{request.user_id}:{request.spell_id}:{self.now}",
                )
            )
        effects = self._effects(target_changes, bool(request.target_player))
        if self.spell.get("morphs") or request.spell_id == MORPH_SPELL:
            account = values.get(RedisKeys.account_data(request.target_username), {})
            if not account or int(account.get("user_id", 0)) != request.target_player:
                return Decision(
                    {"applied": False, "message": "Apariencia del objetivo no disponible."}, {}
                )
            source_changes.update(
                {
                    "morphed_body": account.get("char_race", "1"),
                    "morphed_head": account.get("char_head", "1"),
                    "morphed_until": str(self.now + 300),
                }
            )
            effects = True
        if request.spell_id in HUNGER_SPELLS:
            hunger_key = RedisKeys.player_hunger_thirst(request.target_player)
            hunger = values[hunger_key]
            if not hunger:
                return Decision({"applied": False, "message": "Objetivo inválido."}, {})
            remaining = max(
                0,
                int(hunger.get("min_hunger", 0))
                - (50 if request.spell_id == HUNGER_SPELLS[0] else 100),
            )
            writes[hunger_key] = {
                "min_hunger": str(remaining),
                "hunger_flag": "1" if remaining == 0 else hunger.get("hunger_flag", "0"),
            }
            effects = True
        for attribute in ("strength", "agility"):
            increase, decrease = (
                self.spell.get(f"increases_{attribute}"),
                self.spell.get(f"decreases_{attribute}"),
            )
            if increase or decrease:
                writes[RedisKeys.player_stats(request.target_player)] = {
                    f"{attribute}_modifier_value": str(
                        self.modifier if increase else -self.modifier
                    ),
                    f"{attribute}_modifier_until": str(self.now + (1200 if increase else 700)),
                }
                effects = True
        if request.spell_id == DRAIN_SPELL and hp > 0:
            source_changes["min_hp"] = str(
                min(
                    int(source.get("max_hp", 100)),
                    int(source.get("min_hp", source.get("hp", 0))) + min(hp, amount),
                )
            )
            if "hp" in source:
                source_changes["hp"] = source_changes["min_hp"]
        if not target_changes and not effects:
            return Decision(
                {
                    "applied": False,
                    "message": "Ese hechizo no tiene un efecto válido sobre el objetivo.",
                },
                {},
            )
        writes[target_key] = target_changes
        if source_key == target_key:
            target_changes.update(source_changes)
        else:
            writes[source_key] = source_changes
        return trained_decision(
            Decision(
                {
                    "applied": True,
                    "message": "Hechizo confirmado.",
                    "amount": amount,
                    "hp_delta": int(target_changes.get(hp_field, hp)) - hp,
                    "map_id": int(position["map"]),
                    "source_x": int(position["x"]),
                    "source_y": int(position["y"]),
                    "target_hp": int(target_changes.get(hp_field, hp)),
                    "revived": bool(self.spell.get("revives")),
                    "target_life_id": int(target_changes.get("life_id", target.get("life_id", 0))),
                },
                writes,
            ),
            snapshot,
            request.user_id,
            (("magia", True),),
        )

    def _validate_caster(
        self,
        values: dict[str, dict[str, str]],
        source: dict[str, str],
        position: dict[str, str],
        book: dict[str, str],
    ) -> str | None:
        request = self.request
        if not 1 <= request.x <= MAX_COORD or not 1 <= request.y <= MAX_COORD or not position:
            return "Coordenadas inválidas."
        if (
            int(source.get("min_hp", source.get("hp", 0))) <= 0
            or source.get("death_state") == "pending"
        ):
            return "No puedes lanzar estando muerto."
        if float(source.get("dumb_until", 0)) > time.time():
            return "No puedes lanzar estando aturdido."
        if request.slot and (
            not 1 <= request.slot <= MAX_SLOT
            or book.get(str(request.slot)) != str(request.spell_id)
        ):
            return "El hechizo de ese slot cambió."
        if not request.slot and str(request.spell_id) not in book.values():
            return "No conoces ese hechizo."
        if (
            abs(request.x - int(position.get("x", 0))) + abs(request.y - int(position.get("y", 0)))
            > MAX_RANGE
        ):
            return "El objetivo está demasiado lejos."
        if skill_progress(values[RedisKeys.player_skills(request.user_id)])[0].level < int(
            self.spell.get("min_skill", 0)
        ):
            return "No tienes suficiente magia."
        if int(source.get("min_mana", 0)) < int(self.spell.get("mana_cost", 0)):
            return "No tienes suficiente mana."
        if int(source.get("min_sta", 0)) < int(self.spell.get("stamina_cost", 3)):
            return "No tienes suficiente energía."
        if self.spell.get("need_staff"):
            equipped = values[RedisKeys.player_equipment(request.user_id)]
            inventory = values[RedisKeys.player_inventory(request.user_id)]
            weapon = inventory.get(f"slot_{equipped.get('weapon', '0')}", "")
            from src.utils.inventory_slot import InventorySlot  # noqa: PLC0415

            item = InventorySlot.parse(weapon)
            if item is None or item.item_id not in self.staff_items:
                return "Necesitas un bastón equipado."
        return None

    def _validate_target(
        self,
        source: dict[str, str],
        position: dict[str, str],
        target: dict[str, str],
        target_position: dict[str, str],
    ) -> str | None:
        request = self.request
        if not target or any(
            int(target_position.get(field, -1)) != expected
            for field, expected in (
                ("map", int(position.get("map", 0))),
                ("x", request.x),
                ("y", request.y),
            )
        ):
            return "No hay un objetivo válido en esa posición."
        if request.target_player:
            if int(self.spell.get("target", 3)) == NPC_ONLY_TARGET:
                return "Ese hechizo requiere un NPC."
            if is_hostile(self.spell):
                return self.policy.rejection(
                    request.user_id,
                    request.target_player,
                    position,
                    target_position,
                    source,
                    target,
                )
            if self.spell.get("revives"):
                if (
                    request.target_player == request.user_id
                    or int(target.get("min_hp", target.get("hp", 0))) > 0
                ):
                    return "Sólo puedes resucitar a otro jugador muerto."
            elif int(target.get("min_hp", target.get("hp", 0))) <= 0:
                return "El objetivo está muerto."
        elif int(target.get("hp", 0)) <= 0 or (
            is_hostile(self.spell) and target.get("is_attackable") not in {"True", "1"}
        ):
            return "No puedes afectar a ese NPC."
        elif (
            int(self.spell.get("target", 3)) == 1
            or self.spell.get("revives")
            or any(
                self.spell.get(flag)
                for flag in (
                    "blinds",
                    "dumbs",
                    "makes_invisible",
                    "morphs",
                    "increases_strength",
                    "increases_agility",
                    "decreases_strength",
                    "decreases_agility",
                )
            )
        ):
            return "Ese hechizo requiere un jugador."
        return None

    def _effects(self, changes: dict[str, str], player: bool) -> bool:
        effects = False
        timed = {
            "poisons": ("poisoned_until", 30),
            "paralyzes": (
                "immobilized_until" if player else "paralyzed_until",
                30 if player else 10,
            ),
            "immobilizes": ("immobilized_until" if player else "paralyzed_until", 30),
            "blinds": ("blinded_until", 10),
            "dumbs": ("dumb_until", 30),
            "makes_invisible": ("invisible_until", 60),
        }
        for flag, (field, duration) in timed.items():
            if self.spell.get(flag) and (player or flag in {"poisons", "paralyzes", "immobilizes"}):
                changes[field] = str(self.now + duration)
                if flag == "poisons" and not player:
                    changes["poisoned_by_user_id"] = str(self.request.user_id)
                effects = True
        for flag, fields in {
            "cures_poison": ("poisoned_until",),
            "removes_paralysis": ("immobilized_until" if player else "paralyzed_until",),
            "removes_stupidity": ("dumb_until",),
            "removes_invisibility": ("invisible_until",),
        }.items():
            if self.spell.get(flag):
                changes.update(dict.fromkeys(fields, "0"))
                effects = True
        return effects


async def commit_spell(redis: Redis, identity: str, plan: SpellPlan) -> dict[str, Any]:
    """Confirma el coste una vez con el efecto y resuelve ACK perdido con el mismo ID.

    Returns:
        Resultado original de la intención congelada, sin compensaciones.
    """
    await require_durable(redis)
    result = await transact(
        redis,
        plan.resources,
        identity,
        {"cast": asdict(plan.request), "spell": plan.spell},
        plan.decide,
    )
    await require_durable(redis)
    return result
