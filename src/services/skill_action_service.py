"""Orquesta acciones de habilidades y publica únicamente resultados confirmados."""

import json
from typing import TYPE_CHECKING, Any, cast

from src.models.crafting_data_loader import CRAFTING_KEY
from src.services.combat.physical_plan import PhysicalPlan, PhysicalRequest, commit_physical
from src.services.crafting import craft
from src.services.gathering import GATHERING, gather
from src.services.inventory_notifications import notify_inventory
from src.services.navigation import navigate
from src.services.personal_skills import hide, steal, survival, tame
from src.services.player_progression import publish_progress
from src.services.visual_events import VisualEvents
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.visual_effects import VisualEffectID

SURVIVAL_SKILL = 8
RANGED_SKILL = 18
TAME_SKILL = 17
STEAL_SKILL = 2
MAX_RECIPE_PAGE = 1000


if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.action_cadence import Action, ActionCadence
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_service import NPCService
    from src.services.player.player_death_service import PlayerDeathService
    from src.utils.resource_transaction import Snapshot

RECIPES_PER_PAGE = 4


class SkillActionService:
    """Comparte las reglas entre protocolo extendido y comandos clásicos de trabajo."""

    def __init__(
        self,
        player: PlayerRepository,
        inventory: InventoryRepository,
        terrain: MapResourcesService,
        maps: MapManager,
        catalog: ItemCatalog,
        npcs: NPCService,
        npc_death: NPCDeathService,
        player_death: PlayerDeathService,
        cadence: ActionCadence,
    ) -> None:
        """Recibe servicios únicos; el estado guardado de las acciones vive en Redis."""
        self.player, self.inventory, self.terrain = player, inventory, terrain
        self.maps, self.catalog, self.npcs = maps, catalog, npcs
        self.npc_death, self.player_death, self.cadence = npc_death, player_death, cadence
        self.visual_events = VisualEvents(maps)

    async def execute(
        self,
        user: int,
        action: str,
        params: dict[str, Any],
        sender: MessageSender,
        *,
        identity: str | None = None,
        announce: bool = True,
    ) -> dict[str, Any]:
        """Valida cadencia y coordina una acción autenticada.

        Returns:
            Respuesta autoritativa acotada que puede mostrarse o reintentarse.
        """
        identity = identity or operation_id()
        if action == "recipes":
            return await self._recipes(str(params.get("skill", "")), int(params.get("page", 0)))
        budget: Action = (
            "attack"
            if action == "attack" or (action == "work" and params.get("skill") == RANGED_SKILL)
            else "work"
        )
        if not self.cadence.claim(user, budget):
            return {"applied": False, "message": "Acción demasiado frecuente; espera un instante."}
        try:
            await require_durable(self.player.redis.redis)
            result = await self._dispatch(user, action, params, sender, identity)
            await require_durable(self.player.redis.redis)
            if announce and result.get("message"):
                await sender.send_console_msg(str(result["message"]))
            if result.get("applied"):
                await notify_inventory(sender, self.inventory, user)
                await publish_progress(self.player, user, sender)
                await sender.status_effects.sync_visibility(user, self.player, self.maps)
                if action == "navigate":
                    await self.player_death.publish_state(user)
                    # El cliente habilita pasos sobre agua con este toggle.
                    # Debe ser la última publicación, después de durabilidad.
                    await sender.send_navigate_toggle()
            return result
        finally:
            self.cadence.release(user, budget)

    async def _recipes(self, skill: str, page: int) -> dict[str, Any]:
        if skill not in {"herreria", "carpinteria", "mineria"} or not 0 <= page <= MAX_RECIPE_PAGE:
            return {"applied": False, "message": "Catálogo o página inválidos."}
        rows = json.loads(await self.player.redis.get(CRAFTING_KEY) or "[]")
        rows = [row for row in rows if row["skill"] == skill]
        start = page * RECIPES_PER_PAGE
        for row in rows:
            for material in row["materials"]:
                material["name"] = self.catalog.get_item_name(material["item_id"]) or "Material"
        return {
            "applied": True,
            "kind": "recipes",
            "skill": skill,
            "page": page,
            "has_next": start + RECIPES_PER_PAGE < len(rows),
            "recipes": rows[start : start + RECIPES_PER_PAGE],
        }

    async def _dispatch(
        self,
        user: int,
        action: str,
        params: dict[str, Any],
        sender: MessageSender,
        identity: str,
    ) -> dict[str, Any]:
        if action == "craft":
            return await craft(
                self.player,
                self.inventory,
                self.terrain,
                user,
                str(params["recipe"]),
                int(params["quantity"]),
                identity=identity,
            )
        if action == "hide":
            return await hide(self.player, user, identity)
        if action == "navigate":
            return await self.navigate(user, int(params["slot"]), sender, identity)
        if action not in {"work", "attack"}:
            return {"applied": False, "message": "Acción desconocida."}
        pos = await self.player.get_position(user)
        if pos is None:
            return {"applied": False, "message": "Posición no disponible."}
        skill, x, y = int(params.get("skill", 0)), int(params["x"]), int(params["y"])
        if action == "attack" or skill == RANGED_SKILL:
            return await self._physical(
                user, pos["map"], x, y, sender, identity, ranged=skill == RANGED_SKILL
            )
        if skill in GATHERING:
            return await gather(
                self.player,
                self.inventory,
                self.terrain,
                user,
                skill,
                pos["map"],
                x,
                y,
                identity=identity,
            )
        npc = next(
            (n for n in self.maps.get_npcs_in_map(pos["map"]) if n.x == x and n.y == y), None
        )
        if skill == SURVIVAL_SKILL:
            if npc is None and self.maps.get_ground_items(pos["map"], x, y):
                return {
                    "applied": False,
                    "message": "Necesitas una casilla libre de objetos para la fogata.",
                }
            result = await survival(
                self.player,
                self.inventory,
                self.terrain,
                user,
                pos["map"],
                x,
                y,
                identity,
                npc_id=npc.instance_id if npc else "",
            )
            if result.get("fire"):
                for uid in self.maps.get_players_in_map(pos["map"]):
                    observer = self.maps.get_player_message_sender(uid)
                    if observer:
                        await observer.send_create_fx(user, int(VisualEffectID.MEDITATION), loops=1)
            return result
        if skill == TAME_SKILL and npc:
            all_npcs = await self.npcs.npc_repository.get_all_npcs()
            pets = [n.instance_id for n in all_npcs if n.summoned_by_user_id == user]
            result = await tame(self.player, user, npc.instance_id, pets, identity)
            if result.get("successful"):
                npc.summoned_by_user_id, npc.summoned_until, npc.is_tamed = user, 0.0, True
                npc.is_hostile, npc.movement_type, npc.respawn_time = False, "static", 0
            return result
        target = await self._player_at(pos["map"], x, y, user)
        if skill == STEAL_SKILL and target:
            result = await steal(self.player, self.inventory, self.catalog, user, target, identity)
            observer = self.maps.get_player_message_sender(target)
            if result.get("applied") and observer:
                await observer.send_console_msg("Han intentado robarte.")
                await notify_inventory(observer, self.inventory, target)
                await observer.send_update_user_stats_from_repo(target, self.player)
            return result
        return {"applied": False, "message": "No hay un objetivo válido para esa habilidad."}

    async def _player_at(self, map_id: int, x: int, y: int, exclude: int) -> int:
        for user in self.maps.get_players_in_map(map_id, exclude):
            pos = await self.player.get_position(user)
            if pos and (pos["x"], pos["y"]) == (x, y):
                return user
        return 0

    async def _physical(
        self,
        user: int,
        map_id: int,
        x: int,
        y: int,
        sender: MessageSender,
        identity: str,
        *,
        ranged: bool,
    ) -> dict[str, Any]:
        npc = next((n for n in self.maps.get_npcs_in_map(map_id) if n.x == x and n.y == y), None)
        target = 0 if npc else await self._player_at(map_id, x, y, user)
        if npc is None and not target:
            return {"applied": False, "message": "No hay nada que atacar ahí."}
        plan = PhysicalPlan(
            PhysicalRequest(user, target, npc.instance_id if npc else "", ranged),
            self.catalog,
            self.inventory.MAX_SLOTS,
            self.inventory.stacking.max_stack,
        )
        position = await self.player.get_position(user)
        if position is None:
            return {"applied": False, "message": "Posición no disponible."}

        def guard(snapshot: Snapshot) -> bool:
            source = cast("dict[str, str]", snapshot[RedisKeys.player_position(user)])
            target_position = (
                cast("dict[str, str]", snapshot[RedisKeys.player_position(target)])
                if target
                else cast(
                    "dict[str, str]",
                    snapshot[RedisKeys.npc_instance(npc.instance_id if npc else "")],
                )
            )
            return self.maps.get_player_message_sender(user) is sender and self._clear_path(
                map_id,
                int(source["x"]),
                int(source["y"]),
                int(target_position["x"]),
                int(target_position["y"]),
            )

        plan.world_guard = guard
        result = await commit_physical(self.player.redis.redis, plan, identity)
        if not result.get("applied"):
            return result
        await sender.sync_status(user, self.player)
        amount = int(result["damage"])
        x, y = int(result["target_x"]), int(result["target_y"])
        actor = npc.char_index if npc else target
        kind = 4 if result["critical"] else 0 if amount else 3 if result["blocked"] else 2
        await self.visual_events.damage(identity, map_id, actor, x, y, amount, kind)
        if ranged:
            await self.visual_events.projectile(
                identity,
                map_id,
                user,
                actor,
                int(position["x"]),
                int(position["y"]),
                x,
                y,
                2,
                int(result["projectile_asset"]),
            )
        for uid in self.maps.get_players_in_map(map_id):
            observer = self.maps.get_player_message_sender(uid)
            if observer:
                if amount > 0:
                    await observer.send_create_fx(
                        actor,
                        int(
                            VisualEffectID.CRITICAL_HIT
                            if result["critical"]
                            else VisualEffectID.BLOOD
                        ),
                        loops=1,
                    )
                await observer.send_play_wave(2 if amount else 12, x, y)
        if npc:
            npc.hp = int(result["new_hp"])
            if result["npc_died"]:
                from src.combat.combat_reward_calculator import RewardCalculator  # ruff: ignore[import-outside-top-level]

                await self.npc_death.handle_npc_death(
                    npc,
                    user,
                    RewardCalculator().calculate_experience(npc.level),
                    sender,
                    death_reason="combate",
                )
        elif target:
            observer = self.maps.get_player_message_sender(target)
            if observer:
                await publish_progress(self.player, target, observer)
            if result["player_died"]:
                self.player_death.schedule_death(
                    target, "combate", str(user), expected_life_id=int(result["life_id"])
                )
        return {
            **result,
            "message": f"Has apuñalado al objetivo por {amount} de daño."
            if result["backstab"]
            else f"Golpe crítico: {amount} de daño."
            if result["critical"]
            else f"Has causado {amount} de daño."
            if amount
            else "El objetivo evitó el golpe.",
        }

    def _clear_path(self, map_id: int, x: int, y: int, tx: int, ty: int) -> bool:
        if (x, y) == (tx, ty):
            return False

        def blocks_shot(px: int, py: int) -> bool:
            # El loader bloquea el agua para caminar; no es una pared para disparar.
            return self.terrain.is_blocked(map_id, px, py) and not self.terrain.has_water(
                map_id, px, py
            )

        dx, dy = abs(tx - x), abs(ty - y)
        sx, sy = (1 if tx > x else -1), (1 if ty > y else -1)
        error = dx - dy
        while (x, y) != (tx, ty):
            twice = 2 * error
            nx, ny = x, y
            if twice > -dy:
                error -= dy
                nx += sx
            if twice < dx:
                error += dx
                ny += sy
            if nx != x and ny != y and (blocks_shot(nx, y) or blocks_shot(x, ny)):
                return False
            x, y = nx, ny
            if (x, y) != (tx, ty) and blocks_shot(x, y):
                return False
        return True

    async def navigate(
        self, user: int, slot: int, _sender: MessageSender, identity: str
    ) -> dict[str, Any]:
        """Confirma el cambio; execute publica sólo tras completar durabilidad.

        Returns:
            Resultado de embarcar/desembarcar sin entrenar habilidades manuales.
        """
        return await navigate(
            self.player, self.inventory, self.catalog, self.terrain, user, slot, identity
        )
