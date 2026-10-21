"""Servicio de lógica de negocio para hechizos."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import TYPE_CHECKING, Any

from redis.exceptions import RedisError

from src.constants.gameplay import MAX_PETS
from src.repositories.inventory_repository import InventoryRepository
from src.services.combat.area_spell import AreaSpellPlan
from src.services.combat.pvp_policy import PvpPolicy
from src.services.combat.spell_plan import MAX_COORD, CastRequest, SpellPlan, commit_spell
from src.services.combat.summon_plan import SummonPlan
from src.services.inventory_notifications import notify_inventory
from src.services.player_progression import publish_progress
from src.services.visual_events import VisualEvents
from src.utils.gold_atomic import operation_id

if TYPE_CHECKING:
    from collections.abc import Callable

    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.npc import NPC
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService
    from src.services.player.player_death_service import PlayerDeathService

logger = logging.getLogger(__name__)
MAX_CACHED_CASTS = 4096


class SpellService:
    """Servicio para confirmar magia y publicar su estado autoritativo."""

    def __init__(
        self,
        spell_catalog: SpellCatalog,
        player_repo: PlayerRepository,
        npc_repo: NPCRepository,
        map_manager: MapManager,
        npc_death_service: NPCDeathService | None = None,
        account_repo: AccountRepository | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        npc_service: NPCService | None = None,
        summon_service: SummonService | None = None,
        player_death_service: PlayerDeathService | None = None,
        item_catalog: ItemCatalog | None = None,
    ) -> None:
        """Inicializa el servicio de hechizos.

        Args:
            spell_catalog: Catálogo de hechizos.
            player_repo: Repositorio de jugadores.
            npc_repo: Repositorio de NPCs.
            map_manager: Gestor de mapas.
            npc_death_service: Servicio de muerte de NPCs (opcional).
            account_repo: Repositorio de cuentas (opcional).
            broadcast_service: Servicio de broadcast (opcional).
            npc_service: Servicio de NPCs (opcional).
            summon_service: Servicio de invocación (opcional).
            player_death_service: Liquidación y publicación del ciclo de vida.
            item_catalog: Requisitos de equipo del catálogo propio.
        """
        self.item_catalog = item_catalog
        self.visual_events = VisualEvents(map_manager)
        self.player_death_service = player_death_service
        self._plans: dict[str, SpellPlan] = {}
        self._publish_locks: dict[str, asyncio.Lock] = {}
        self._published: set[str] = set()
        self.spell_catalog = spell_catalog
        self.player_repo = player_repo
        self.npc_repo = npc_repo
        self.map_manager = map_manager
        self.npc_death_service = npc_death_service
        self.account_repo = account_repo
        self.broadcast_service = broadcast_service
        self.npc_service = npc_service
        self.summon_service = summon_service

    async def cast_spell(
        self,
        user_id: int,
        spell_id: int,
        target_x: int,
        target_y: int,
        message_sender: MessageSender,
        *,
        identity: str | None = None,
        slot: int = 0,
    ) -> bool:
        """Confirma coste y efectos conjuntamente después de revalidar el snapshot.

        Returns:
            True sólo si el recibo confirma el cast; nunca compensa un EXEC incierto.
        """
        if self.map_manager.get_player_message_sender(user_id) is not message_sender:
            return False
        identity = identity or operation_id()
        spell = self.spell_catalog.get_spell_data(spell_id)
        if not spell:
            await message_sender.send_console_msg("No existe ese hechizo.")
            return False
        plan = self._plans.get(identity)
        if plan is None:
            position = await self.player_repo.get_position(user_id)
            if not position:
                return False
            npc, player = (
                (None, None)
                if spell.get("area")
                else await self._find_target(
                    position["map"], target_x, target_y, user_id, spell, message_sender
                )
            )
            if npc is None and player is None and not spell.get("area"):
                return False
            request = CastRequest(
                user_id,
                spell_id,
                target_x,
                target_y,
                slot,
                player or 0,
                npc.instance_id if npc else "",
                self.map_manager.get_player_username(player) or "" if player else "",
            )
            if spell.get("area"):
                targets = await self._area_targets(request, spell, position["map"])
                plan = AreaSpellPlan(
                    request, dict(spell, id=spell_id), PvpPolicy.configured(), targets
                )
            elif spell.get("invokes") or spell.get("warps_pet"):
                plan = await self._prepare_summon(
                    identity, request, dict(spell, id=spell_id), position["map"]
                )
                if plan is None:
                    await message_sender.send_console_msg(
                        "No hay una mascota, plantilla o lugar válido para ese hechizo."
                    )
                    return False
            else:
                plan = SpellPlan(request, dict(spell, id=spell_id), PvpPolicy.configured())
            if self.item_catalog:
                plan.staff_items = self.item_catalog.staff_item_ids()
                plan.item_catalog = self.item_catalog
            target_sender = self.map_manager.get_player_message_sender(player) if player else None
            source_sender = self.map_manager.get_player_message_sender(user_id)
            plan.world_guard = lambda: (
                self.map_manager.get_player_message_sender(user_id) is source_sender
                and (
                    player is None
                    or self.map_manager.get_player_message_sender(player) is target_sender
                )
            )
            if isinstance(plan, SummonPlan):
                session_guard: Callable[[], bool] | None = plan.world_guard
                plan.world_guard = lambda: (
                    (session_guard is None or session_guard())
                    and all(
                        self.map_manager.can_move_to(
                            plan.map_id, x, y, reservation=plan.reservation_id
                        )
                        for x, y in plan.positions
                    )
                )
            plan.event_id = identity
            self._remember_plan(identity, plan)
        elif (
            plan.request.user_id != user_id
            or plan.request.spell_id != spell_id
            or (plan.request.x, plan.request.y, plan.request.slot) != (target_x, target_y, slot)
        ):
            await message_sender.send_console_msg(
                "Identificador de cast reutilizado para otra intención."
            )
            return False
        try:
            result = await commit_spell(self.player_repo.redis.redis, identity, plan)
        except RedisError, RuntimeError, ValueError:
            await message_sender.send_console_msg(
                "Cast sin confirmar. Consulta el estado antes de intentarlo de nuevo."
            )
            logger.warning("Cast %s sin confirmar", identity)
            return False
        if not result["applied"]:
            self.map_manager.release_positions(identity)
            await message_sender.send_console_msg(result["message"])
            return False
        async with self._publish_locks.setdefault(identity, asyncio.Lock()):
            if identity not in self._published:
                await self._publish_committed(plan, result, message_sender)
                self.map_manager.release_positions(identity)
                self._published.add(identity)
        return True

    def _remember_plan(self, identity: str, plan: SpellPlan) -> None:
        """Mantiene el cache acotado y libera reservas de un plan desalojado."""
        self._plans[identity] = plan
        if len(self._plans) > MAX_CACHED_CASTS:
            oldest = next(iter(self._plans))
            self.map_manager.release_positions(oldest)
            del self._plans[oldest]
            self._published.discard(oldest)
            self._publish_locks.pop(oldest, None)

    async def _area_targets(
        self, request: CastRequest, spell: dict[str, Any], map_id: int
    ) -> list[CastRequest]:
        """Selecciona una lista única y estable desde entidades reales del mapa.

        Returns:
            Candidatos dentro de la forma; vida/posición/PvP se revalidan en EXEC.
        """
        area = spell["area"]
        rows = []

        def inside(x: int, y: int) -> bool:
            dx, dy = abs(x - request.x), abs(y - request.y)
            return bool(
                (max(dx, dy) if area.get("shape", "diamond") == "square" else dx + dy)
                <= area["radius"]
            )

        if area["targets"] in {"players", "both"}:
            for user in sorted(set(self.map_manager.get_players_in_map(map_id))):
                pos = await self.player_repo.get_position(user)
                if pos and pos["map"] == map_id and inside(pos["x"], pos["y"]):
                    rows.append(
                        replace(
                            request,
                            x=pos["x"],
                            y=pos["y"],
                            target_player=user,
                            target_username=self.map_manager.get_player_username(user) or "",
                        )
                    )
        if area["targets"] in {"npcs", "both"}:
            rows.extend(
                replace(request, x=npc.x, y=npc.y, target_npc=npc.instance_id)
                for npc in sorted(
                    self.map_manager.get_npcs_in_map(map_id), key=lambda npc: npc.instance_id
                )
                if inside(npc.x, npc.y)
            )
        return rows

    async def _prepare_summon(
        self, identity: str, request: CastRequest, spell: dict[str, Any], map_id: int
    ) -> SummonPlan | None:
        """Prepara plantillas y terreno sin crear criaturas ni cobrar recursos.

        Returns:
            Plan completo o None si la invocación no es válida.
        """
        if not self.npc_service or not self.summon_service:
            return None
        pet_ids = await self.summon_service.get_player_pets(request.user_id)
        pets = [npc for key in pet_ids if (npc := await self.npc_repo.get_npc(key)) is not None]
        count = min(int(spell.get("invoke_count", 1)), MAX_PETS - len(pets))
        occupants = self.map_manager.get_npcs_in_map(map_id)
        occupied_players = set()
        for player_id in self.map_manager.get_players_in_map(map_id):
            player_position = await self.player_repo.get_position(player_id)
            if player_position and player_position["map"] == map_id:
                occupied_players.add((player_position["x"], player_position["y"]))
        positions = []
        center_x, center_y = request.x, request.y
        if spell.get("warps_pet"):
            owner = await self.player_repo.get_position(request.user_id)
            if not pets or not owner:
                return None
            center_x, center_y = owner["x"], owner["y"]
        for dx, dy in (
            (0, 0),
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (1, 1),
            (-1, 1),
            (1, -1),
        ):
            x, y = center_x + dx, center_y + dy
            if (
                1 <= x <= MAX_COORD
                and 1 <= y <= MAX_COORD
                and (x, y) not in occupied_players
                and self.map_manager.can_move_to(map_id, x, y)
                and all((npc.x, npc.y) != (x, y) for npc in occupants)
            ):
                positions.append((x, y))
        positions = positions[: 1 if spell.get("warps_pet") else max(0, count)]
        if not positions:
            return None
        plan = SummonPlan(request, spell, PvpPolicy.configured())
        plan.prepare(
            identity,
            map_id,
            pets,
            int(spell.get("invoke_npc_id", 0)),
            self.npc_service.npc_catalog,
            positions,
            self.npc_service.reserve_character_indices(len(positions)),
            occupants,
            list(self.map_manager.get_players_in_map(map_id)),
        )
        try:
            self.map_manager.reserve_positions(identity, map_id, positions)
        except ValueError:
            return None
        return plan

    async def _publish_committed(  # ruff: ignore[too-many-locals, too-many-statements] - publicación de un único recibo de magia
        self,
        plan: SpellPlan,
        result: dict[str, Any],
        sender: MessageSender,
        *,
        announce: bool = True,
        sync_caster: bool = True,
    ) -> None:
        """Publica estado confirmado y repara caché desde Redis, sin repetir efectos."""
        request, spell = plan.request, plan.spell
        if isinstance(plan, AreaSpellPlan):
            for outcome in result.get("area_results", []):
                child_request = CastRequest(**outcome["request"])
                child = next(target for target in plan.targets if target.request == child_request)
                child.event_id = (
                    f"{plan.event_id}:{child_request.target_player or child_request.target_npc}"
                )
                await self._publish_committed(
                    child, outcome["result"], sender, announce=False, sync_caster=False
                )
            await sender.sync_status(request.user_id, self.player_repo)
            await publish_progress(self.player_repo, request.user_id, sender)
            await sender.send_console_msg(f"Has lanzado {spell.get('name', 'un hechizo')}.")
            return
        if spell.get("components") and plan.charge_cost:
            # El inventario publicado proviene del mismo commit que cobró el cast.
            await notify_inventory(
                sender, InventoryRepository(self.player_repo.redis), request.user_id
            )
        delta = int(result.get("hp_delta", 0))
        actor = request.target_player
        if request.target_npc:
            target_npc = await self.npc_repo.get_npc(request.target_npc)
            actor = target_npc.char_index if target_npc else 0
            if delta < 0 and target_npc and target_npc.snd2 and self.broadcast_service:
                await self.broadcast_service.broadcast_play_wave(
                    map_id=target_npc.map_id,
                    wave_id=target_npc.snd2,
                    x=target_npc.x,
                    y=target_npc.y,
                )
        if actor and result.get("map_id"):
            identity = plan.event_id or operation_id()
            map_id = int(result["map_id"])
            if delta:
                await self.visual_events.damage(
                    identity, map_id, actor, request.x, request.y, abs(delta), 1 if delta > 0 else 0
                )
            await self.visual_events.projectile(
                identity,
                map_id,
                request.user_id,
                actor,
                int(result["source_x"]),
                int(result["source_y"]),
                request.x,
                request.y,
                1,
                int(spell.get("fx_grh", 0)),
                request.spell_id,
            )
        if sync_caster:
            await sender.sync_status(request.user_id, self.player_repo)
            await publish_progress(self.player_repo, request.user_id, sender)
        actors = []
        if request.target_player:
            actors.append((request.target_player, request.x, request.y))
        elif request.target_npc:
            target = await self.npc_repo.get_npc(request.target_npc)
            if target:
                actors.append((target.char_index, target.x, target.y))
        if result.get("pets"):
            actors = []
            for pet_id in result["pets"]:
                pet = await self.npc_repo.get_npc(pet_id)
                if pet:
                    actors.append((pet.char_index, pet.x, pet.y))
                    old_map = int(result.get("old_maps", {}).get(pet_id, pet.map_id))
                    if result.get("warped"):
                        self.map_manager.remove_npc(old_map, pet_id)
                        if self.broadcast_service:
                            await self.broadcast_service.broadcast_character_remove(
                                old_map, pet.char_index
                            )
                    if isinstance(plan, SummonPlan):
                        self.map_manager.release_positions(
                            plan.reservation_id, (pet.map_id, pet.x, pet.y)
                        )
                    self.map_manager.add_npc(pet.map_id, pet)
                    if self.broadcast_service:
                        await self.broadcast_service.broadcast_character_create(
                            map_id=pet.map_id,
                            char_index=pet.char_index,
                            body=pet.body_id,
                            head=pet.head_id,
                            heading=pet.heading,
                            x=pet.x,
                            y=pet.y,
                            name=pet.name,
                        )
            await self._publish_spell_media(request.user_id, spell, actors, sender)
            await sender.send_console_msg(f"Has lanzado {spell.get('name', 'un hechizo')}.")
            return
        if request.target_player:
            target_sender = self.map_manager.get_player_message_sender(request.target_player)
            if target_sender:
                await target_sender.send_update_user_stats_from_repo(
                    request.target_player, self.player_repo
                )
                await target_sender.sync_status(request.target_player, self.player_repo)
                if spell.get("makes_invisible") or spell.get("removes_invisibility"):
                    await target_sender.send_set_invisible(
                        request.target_player, invisible=bool(spell.get("makes_invisible"))
                    )
                if any(
                    spell.get(flag)
                    for flag in (
                        "increases_strength",
                        "decreases_strength",
                        "increases_agility",
                        "decreases_agility",
                    )
                ):
                    attributes = await self.player_repo.get_player_attributes(request.target_player)
                    if attributes:
                        await target_sender.send_update_strength_and_dexterity(
                            attributes.strength, attributes.agility
                        )
                if request.spell_id in {12, 13}:
                    hunger = await self.player_repo.get_hunger_thirst(request.target_player)
                    if hunger:
                        await target_sender.send_update_hunger_and_thirst(
                            hunger["max_water"],
                            hunger["min_water"],
                            hunger["max_hunger"],
                            hunger["min_hunger"],
                        )
            if self.player_death_service:
                if result["target_hp"] <= 0:
                    self.player_death_service.schedule_death(
                        request.target_player,
                        "magia",
                        "hechizo",
                        expected_life_id=int(result["target_life_id"]),
                    )
                elif result.get("revived"):
                    await self.player_death_service.publish_state(request.target_player)
            if self.player_death_service and (
                spell.get("makes_invisible")
                or spell.get("removes_invisibility")
                or spell.get("morphs")
            ):
                await self.player_death_service.publish_state(
                    request.user_id if spell.get("morphs") else request.target_player
                )
        else:
            npc = await self.npc_repo.get_npc(request.target_npc)
            if npc:
                current = next(
                    (
                        row
                        for row in self.map_manager.get_npcs_in_map(npc.map_id)
                        if row.instance_id == npc.instance_id
                    ),
                    None,
                )
                if current:
                    (
                        current.hp,
                        current.paralyzed_until,
                        current.poisoned_until,
                        current.poisoned_by_user_id,
                    ) = npc.hp, npc.paralyzed_until, npc.poisoned_until, npc.poisoned_by_user_id
                if npc.hp <= 0 and self.npc_death_service:
                    await self.npc_death_service.handle_npc_death(
                        npc, request.user_id, npc.level * 10, sender, death_reason="hechizo"
                    )
        await self._publish_spell_media(request.user_id, spell, actors, sender)
        if announce:
            await sender.send_console_msg(f"Has lanzado {spell.get('name', 'un hechizo')}.")

    async def _publish_spell_media(
        self,
        user_id: int,
        spell: dict[str, Any],
        actors: list[tuple[int, int, int]],
        sender: MessageSender,
    ) -> None:
        """Publica FX del actor real y sonido una vez por lanzamiento en su mapa."""
        position = await self.player_repo.get_position(user_id)
        if not position or not actors:
            return
        observers = self.map_manager.get_all_message_senders_in_map(position["map"]) or [sender]
        fx, wave = int(spell.get("fx_grh", 0)), int(spell.get("wav", 0))
        for observer in observers:
            if fx > 0:
                for char_index, _x, _y in actors:
                    await observer.send_create_fx(char_index, fx, int(spell.get("loops", 0)))
            if wave > 0:
                await observer.send_play_wave(wave, actors[0][1], actors[0][2])

    async def _find_target(
        self,
        map_id: int,
        target_x: int,
        target_y: int,
        user_id: int,
        spell_data: dict[str, Any],
        message_sender: MessageSender,
    ) -> tuple[NPC | None, int | None]:
        """Busca el target del hechizo (NPC o jugador).

        Returns:
            Tupla (target_npc, target_player_id), ambos pueden ser None.
        """
        target_npc = None
        target_player_id = None

        # Los hechizos de terreno no requieren una criatura en el tile elegido.
        if spell_data.get("invokes") or spell_data.get("warps_pet"):
            return None, user_id

        # Buscar NPCs
        for npc in self.map_manager.get_npcs_in_map(map_id):
            if npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        # Si no hay NPC, buscar jugadores
        if not target_npc:
            for player_id in self.map_manager.get_players_in_map(map_id):
                player_pos = await self.player_repo.get_position(player_id)
                if (
                    player_pos
                    and player_pos["x"] == target_x
                    and player_pos["y"] == target_y
                    and player_pos["map"] == map_id
                ):
                    target_player_id = player_id
                    break

        if not target_npc and not target_player_id:
            position = await self.player_repo.get_position(user_id)
            if position and position["x"] == target_x and position["y"] == target_y:
                target_player_id = user_id
            else:
                await message_sender.send_console_msg("No hay objetivo válido en esa posición.")
                return None, None

        return target_npc, target_player_id
