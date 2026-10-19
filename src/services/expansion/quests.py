"""Misiones persistidas: objetivos, entrega y premio confirman con sus recursos."""

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.models.item_constants import MAX_PLAYER_GOLD
from src.services.combat.spell_components import take_materials
from src.services.expansion.pages import QUEST_ROW_BUDGET, bounded_pages
from src.services.player_progression import level_changes
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact
from src.utils.slot_plan import SlotPlan

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.models.npc import NPC
    from src.services.expansion.catalog import ExpansionCatalog, Quest
    from src.services.expansion.factions import FactionService

MAX_ACTIVE = 5
PAGE_SIZE = 2
EVENT_RETENTION = 604800
NPC_CONVERSATION_RANGE = 2
MAX_CHARACTER_EXPERIENCE = 2147483647


def decode_progress(value: str | None) -> dict[str, Any]:
    """Decodifica un registro de progreso propio del servidor.

    Returns:
        Registro existente o estado ofrecido sin progreso.
    """
    return (
        cast("dict[str, Any]", json.loads(value))
        if value
        else {"status": "available", "progress": []}
    )


class QuestService:
    """No acepta cantidades de progreso, premios ni bajas suministradas por clientes."""

    def __init__(
        self, deps: DependencyContainer, catalog: ExpansionCatalog, factions: FactionService
    ) -> None:
        """Comparte catálogos e infraestructura ya inicializados."""
        self.deps, self.catalog, self.factions = deps, catalog, factions

    def requirements(self, quest: Quest, stats: dict[str, str], journal: dict[str, str]) -> bool:
        """Comprueba los requisitos sobre el snapshot observado.

        Returns:
            Si se cumplen nivel, clase, facción y prerrequisitos cobrados.
        """
        return (
            int(stats.get("level", 0)) >= quest.min_level
            and (not quest.classes or int(stats.get("class_id", 0)) in quest.classes)
            and (not quest.faction or stats.get("faction_id", "neutral") == quest.faction)
            and all(
                decode_progress(journal.get(key))["status"] == "claimed"
                for key in quest.prerequisites
            )
        )

    async def npc(self, user: int, char_index: int) -> NPC | None:
        """Resuelve únicamente instancias del mapa visible del actor.

        Returns:
            Instancia autoritativa o None si el índice ya no pertenece al mapa.
        """
        position = await self.deps.player_repo.get_position(user)
        if not position:
            return None
        map_id = position["map"]
        return next(
            (
                npc
                for npc in self.deps.map_manager.get_npcs_in_map(map_id)
                if npc.char_index == char_index
            ),
            None,
        )

    @staticmethod
    def nearby(position: dict[str, str], npc: dict[str, str]) -> bool:
        """Comprueba alcance real de conversación.

        Returns:
            Si el NPC está a dos tiles como máximo, en el mismo mapa.
        """
        return bool(
            npc
            and int(position.get("map", 0)) == int(npc.get("map_id", -1))
            and max(
                abs(int(position.get("x", 0)) - int(npc.get("x", 0))),
                abs(int(position.get("y", 0)) - int(npc.get("y", 0))),
            )
            <= NPC_CONVERSATION_RANGE
        )

    async def snapshot(self, user: int, params: dict[str, Any]) -> dict[str, Any]:
        """Página de diario y ofertas autorizadas de un NPC cercano.

        Returns:
            Estados, objetivos y premios públicos con acciones calculadas.
        """
        journal = cast(
            "dict[str, str]", await self.deps.redis_client.redis.hgetall(f"quests:{user}")
        )
        stats = cast(
            "dict[str, str]",
            await self.deps.redis_client.redis.hgetall(RedisKeys.player_user_stats(user)),
        )
        position = cast(
            "dict[str, str]",
            await self.deps.redis_client.redis.hgetall(RedisKeys.player_position(user)),
        )
        target = await self.npc(user, int(params.get("npc", 0)))
        if target is None and not int(params.get("npc", 0)):
            wanted = {q.start_npc for q in self.catalog.quests.values()} | {
                q.finish_npc for q in self.catalog.quests.values()
            }
            target = next(
                (
                    npc
                    for npc in self.deps.map_manager.get_npcs_in_map(int(position.get("map", 0)))
                    if npc.npc_id in wanted
                    and max(
                        abs(npc.x - int(position.get("x", 0))),
                        abs(npc.y - int(position.get("y", 0))),
                    )
                    <= NPC_CONVERSATION_RANGE
                ),
                None,
            )
        npc_data = (
            cast(
                "dict[str, str]",
                await self.deps.redis_client.redis.hgetall(
                    RedisKeys.npc_instance(target.instance_id)
                ),
            )
            if target
            else {}
        )
        near = self.nearby(position, npc_data)
        rows = []
        for quest in self.catalog.quests.values():
            saved = decode_progress(journal.get(quest.id))
            allowed = self.requirements(quest, stats, journal)
            start = near and int(npc_data.get("npc_id", 0)) == quest.start_npc
            finish = near and int(npc_data.get("npc_id", 0)) == quest.finish_npc
            if int(params.get("npc", 0)) and not (start or finish):
                continue
            progress = saved.get("progress", [0] * len(quest.objectives))
            if len(progress) != len(quest.objectives):
                progress = [0] * len(quest.objectives)
            rows.append(
                {
                    "id": quest.id,
                    "title": quest.title,
                    "description": quest.description,
                    "status": saved["status"]
                    if saved["status"] not in {"available", "abandoned"} or allowed
                    else "locked",
                    "objectives": [
                        {**obj.model_dump(), "progress": progress[index]}
                        for index, obj in enumerate(quest.objectives)
                    ],
                    "gold": quest.gold,
                    "experience": quest.experience,
                    "rewards": [reward.model_dump() for reward in quest.rewards],
                    "accept": start and allowed and saved["status"] in {"available", "abandoned"},
                    "deliver": finish
                    and saved["status"] == "active"
                    and any(obj.kind == "deliver" for obj in quest.objectives),
                    "claim": finish and saved["status"] == "completed",
                    "abandon": saved["status"] == "active",
                }
            )
        chunks = bounded_pages(rows, PAGE_SIZE, QUEST_ROW_BUDGET)
        page = min(max(0, int(params.get("page", 0))), len(chunks) - 1)
        return {
            "rows": chunks[page],
            "page": page,
            "pages": len(chunks),
            "npc": target.char_index if target and near else 0,
            "max_active": MAX_ACTIVE,
        }

    async def command(
        self, user: int, action: str, params: dict[str, Any], identity: str
    ) -> dict[str, Any]:
        """Confirma aceptación, abandono, materiales o premios en un único EXEC.

        Returns:
            Resultado idempotente, sin premios parciales ni cobros repetidos.
        """
        quest = self.catalog.quests.get(str(params.get("quest", "")))
        if quest is None:
            return {"applied": False, "message": "Misión desconocida."}
        target = await self.npc(user, int(params.get("npc", 0)))
        keys = {
            "journal": f"quests:{user}",
            "stats": RedisKeys.player_user_stats(user),
            "bag": RedisKeys.player_inventory(user),
            "position": RedisKeys.player_position(user),
            "gear": RedisKeys.player_equipment(user),
            "attrs": RedisKeys.player_stats(user),
            "skills": RedisKeys.player_skills(user),
            "npc": RedisKeys.npc_instance(target.instance_id) if target else "",
        }

        def decide(snapshot: Snapshot) -> Decision:
            journal = cast("dict[str, str]", snapshot[keys["journal"]])
            stats = cast("dict[str, str]", snapshot[keys["stats"]])
            current = decode_progress(journal.get(quest.id))
            status = current["status"]
            if int(stats.get("min_hp", 0)) <= 0:
                return Decision({"applied": False, "message": "Debes estar vivo."}, {})
            npc_data = cast("dict[str, str]", snapshot.get(keys["npc"], {}))
            near = self.nearby(cast("dict[str, str]", snapshot[keys["position"]]), npc_data)
            expected = quest.start_npc if action == "accept" else quest.finish_npc
            if action != "abandon" and (not near or int(npc_data.get("npc_id", 0)) != expected):
                return Decision(
                    {"applied": False, "message": "Debes hablar con el NPC de esta misión."}, {}
                )
            writes: dict[str, str | dict[str, str]] = {}
            if action == "accept":
                if status in {"active", "completed"}:
                    return Decision({"applied": True, "message": "La misión ya está aceptada."}, {})
                if (
                    status == "claimed"
                    or not self.requirements(quest, stats, journal)
                    or sum(
                        decode_progress(value)["status"] in {"active", "completed"}
                        for value in journal.values()
                    )
                    >= MAX_ACTIVE
                ):
                    return Decision(
                        {
                            "applied": False,
                            "message": (
                                "No cumples los requisitos o alcanzaste el cupo de misiones."
                            ),
                        },
                        {},
                    )
                current = {
                    "status": "active",
                    "progress": [0] * len(quest.objectives),
                    "accepted_at": time.time(),
                }
            elif action == "abandon":
                if status != "active":
                    return Decision(
                        {"applied": False, "message": "Sólo puedes abandonar una misión activa."},
                        {},
                    )
                current = {**current, "status": "abandoned"}
            elif action == "deliver":
                if status != "active":
                    return Decision({"applied": False, "message": "La misión no está activa."}, {})
                progress = list(current["progress"])
                requirements = [
                    (objective.target, objective.quantity - int(progress[index]))
                    for index, objective in enumerate(quest.objectives)
                    if objective.kind == "deliver" and objective.quantity > int(progress[index])
                ]
                try:
                    fields = take_materials(
                        cast("dict[str, str]", snapshot[keys["bag"]]),
                        cast("dict[str, str]", snapshot[keys["gear"]]),
                        requirements,
                    )
                except ValueError as error:
                    return Decision({"applied": False, "message": str(error)}, {})
                for index, objective in enumerate(quest.objectives):
                    if objective.kind == "deliver":
                        progress[index] = objective.quantity
                current = {
                    **current,
                    "progress": progress,
                    "status": "completed"
                    if all(progress[i] >= obj.quantity for i, obj in enumerate(quest.objectives))
                    else "active",
                }
                writes[keys["bag"]] = fields
            elif action == "claim":
                if status != "completed":
                    return Decision(
                        {
                            "applied": False,
                            "message": "La misión no está completada o el premio ya fue cobrado.",
                        },
                        {},
                    )
                try:
                    writes.update(self._rewards(quest, stats, snapshot, keys))
                except ValueError as error:
                    return Decision({"applied": False, "message": str(error)}, {})
                current = {**current, "status": "claimed", "claimed_at": time.time()}
            else:
                return Decision({"applied": False, "message": "Acción de misión desconocida."}, {})
            writes[keys["journal"]] = {quest.id: json.dumps(current, separators=(",", ":"))}
            return Decision({"applied": True, "message": "Misión actualizada."}, writes)

        return await transact(
            self.deps.redis_client.redis,
            tuple(Resource(key, "hash") for key in keys.values() if key),
            identity,
            {
                "quest": quest.id,
                "action": action,
                "npc": target.instance_id if target else "",
                "user": user,
            },
            decide,
        )

    def _rewards(
        self, quest: Quest, stats: dict[str, str], snapshot: Snapshot, keys: dict[str, str]
    ) -> dict[str, dict[str, str]]:
        """Prepara premios y crecimiento juntos, sin escrituras parciales.

        Returns:
            Cambios confirmables en el mismo EXEC que marca la misión cobrada.

        Raises:
            ValueError: Por saldo/experiencia desbordados o inventario completo.
        """
        gold = int(stats.get("gold", 0)) + quest.gold
        experience = int(stats.get("experience", 0)) + quest.experience
        if gold > MAX_PLAYER_GOLD or experience > MAX_CHARACTER_EXPERIENCE:
            message = "El premio supera tu límite de oro o experiencia."
            raise ValueError(message)
        bag = SlotPlan(
            cast("dict[str, str]", snapshot[keys["bag"]]),
            30,
            self.deps.inventory_repo.stacking.max_stack,
        )
        for reward in quest.rewards:
            bag.give(reward.item_id, reward.quantity)
        enriched = {**stats, "gold": str(gold), "experience": str(experience)}
        levels, skills, _ = level_changes(
            enriched,
            cast("dict[str, str]", snapshot[keys["attrs"]]),
            cast("dict[str, str]", snapshot[keys["skills"]]),
        )
        return {
            keys["bag"]: bag.fields(),
            keys["stats"]: {**enriched, **levels, **self.factions.prestige(stats, "quest_claim")},
            keys["skills"]: skills,
        }

    async def record_kill(self, npc: NPC, user: int) -> None:
        """Atribuye sólo el golpe final del jugador, una vez por instancia y mismo mapa."""
        if user < 1 or npc.is_tamed or npc.summoned_by_user_id:
            return
        journal_key, event_key = f"quests:{user}", f"quest-event:{npc.instance_id}"
        stats_key, position_key, npc_key = (
            RedisKeys.player_user_stats(user),
            RedisKeys.player_position(user),
            RedisKeys.npc_instance(npc.instance_id),
        )

        def decide(snapshot: Snapshot) -> Decision:
            event = cast("dict[str, str]", snapshot[event_key])
            instance = cast("dict[str, str]", snapshot[npc_key])
            position = cast("dict[str, str]", snapshot[position_key])
            if (
                event.get("credited")
                or not instance
                or int(instance.get("hp", 1)) > 0
                or int(position.get("map", 0)) != npc.map_id
            ):
                return Decision({"applied": False}, {})
            journal = cast("dict[str, str]", snapshot[journal_key])
            changes = {}
            for key, saved in journal.items():
                quest = self.catalog.quests.get(key)
                current = decode_progress(saved)
                if not quest or current["status"] != "active":
                    continue
                progress = list(current["progress"])
                for index, objective in enumerate(quest.objectives):
                    if objective.kind == "kill" and objective.target == npc.npc_id:
                        progress[index] = min(objective.quantity, int(progress[index]) + 1)
                state = (
                    "completed"
                    if all(progress[i] >= obj.quantity for i, obj in enumerate(quest.objectives))
                    else "active"
                )
                changes[key] = json.dumps(
                    {**current, "progress": progress, "status": state}, separators=(",", ":")
                )
            stats = cast("dict[str, str]", snapshot[stats_key])
            return Decision(
                {"applied": True},
                {
                    journal_key: changes,
                    event_key: {"credited": str(user)},
                    stats_key: self.factions.prestige(stats, "npc_kill")
                    if npc.is_hostile and not npc.summoned_by_user_id
                    else {},
                },
            )

        await transact(
            self.deps.redis_client.redis,
            (
                Resource(journal_key, "hash"),
                Resource(event_key, "hash", ttl_seconds=EVENT_RETENTION),
                Resource(stats_key, "hash"),
                Resource(position_key, "hash"),
                Resource(npc_key, "hash"),
            ),
            operation_id(),
            {"npc_kill": npc.instance_id, "user": user},
            decide,
        )
