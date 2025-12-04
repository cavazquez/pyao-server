"""Efectos especiales de hechizos (hambre, mascota, invocación)."""

from __future__ import annotations

import logging

from src.constants.gameplay import MAX_PETS
from src.game.map_manager import MAX_COORDINATE
from src.services.player.spell_effects.base import SpellContext, SpellEffect, SpellEffectResult

logger = logging.getLogger(__name__)

# IDs de hechizos de hambre
SPELL_ID_HUNGER_ATTACK = 12
SPELL_ID_IGOR_HUNGER = 13

# Reducción de hambre
HUNGER_ATTACK_REDUCTION = 50
IGOR_HUNGER_REDUCTION = 100

# Duración de invocación (segundos)
SUMMON_DURATION_SECONDS = 300.0


class HungerEffect(SpellEffect):
    """Efecto de reducir hambre."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si es un hechizo de hambre."""
        return ctx.spell_id in {SPELL_ID_HUNGER_ATTACK, SPELL_ID_IGOR_HUNGER}

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """NPCs no tienen hambre."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Reduce hambre de un jugador."""
        if not ctx.target_player_id or not ctx.player_repo:
            return SpellEffectResult(success=False)

        hunger_thirst = await ctx.player_repo.get_hunger_thirst(ctx.target_player_id)
        if not hunger_thirst:
            return SpellEffectResult(success=False)

        current_hunger = hunger_thirst["min_hunger"]
        max_hunger = hunger_thirst["max_hunger"]

        # Determinar reducción según el hechizo
        if ctx.spell_id == SPELL_ID_HUNGER_ATTACK:
            hunger_reduction = HUNGER_ATTACK_REDUCTION
        else:
            hunger_reduction = IGOR_HUNGER_REDUCTION

        # Reducir hambre
        new_hunger = max(0, current_hunger - hunger_reduction)
        hunger_flag = 1 if new_hunger <= 0 else hunger_thirst.get("hunger_flag", 0)

        # Actualizar hambre
        await ctx.player_repo.set_hunger_thirst(
            user_id=ctx.target_player_id,
            max_water=hunger_thirst["max_water"],
            min_water=hunger_thirst["min_water"],
            max_hunger=max_hunger,
            min_hunger=new_hunger,
            thirst_flag=hunger_thirst.get("thirst_flag", 0),
            hunger_flag=hunger_flag,
            water_counter=hunger_thirst.get("water_counter", 0),
            hunger_counter=hunger_thirst.get("hunger_counter", 0),
        )

        # Enviar actualización al target
        target_sender = await ctx.get_target_message_sender()
        if target_sender:
            await target_sender.send_update_hunger_and_thirst(
                max_water=hunger_thirst["max_water"],
                min_water=hunger_thirst["min_water"],
                max_hunger=max_hunger,
                min_hunger=new_hunger,
            )

        logger.info(
            "Jugador user_id %d hambre reducida en %d (de %d a %d) por hechizo %s",
            ctx.target_player_id,
            hunger_reduction,
            current_hunger,
            new_hunger,
            ctx.spell_name,
        )

        return SpellEffectResult(success=True, data={"hunger_reduction": hunger_reduction})


class WarpPetEffect(SpellEffect):
    """Efecto de teletransportar mascota."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo teletransporta mascota."""
        return ctx.spell_data.get("warps_pet", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """No aplica a NPCs."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Teletransporta la mascota del caster a su posición."""
        if not ctx.npc_service or not ctx.summon_service or not ctx.player_repo:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(
                    "El sistema de invocación no está disponible."
                )
            return SpellEffectResult(success=False)

        # Obtener posición del caster
        caster_position = await ctx.player_repo.get_position(ctx.user_id)
        if not caster_position:
            return SpellEffectResult(success=False)

        map_id = caster_position["map"]
        caster_x = caster_position["x"]
        caster_y = caster_position["y"]

        # Obtener mascotas del jugador
        player_pets = await ctx.summon_service.get_player_pets(ctx.user_id)
        if not player_pets or not ctx.npc_repo:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg("No tienes mascotas invocadas.")
            return SpellEffectResult(success=False)

        # Obtener el NPC desde el instance_id
        pet_instance_id = player_pets[0]
        pet_npc = await ctx.npc_repo.get_npc(pet_instance_id)

        if not pet_npc:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg("No se pudo encontrar la mascota.")
            return SpellEffectResult(success=False)

        old_map_id = pet_npc.map_id
        old_x = pet_npc.x
        old_y = pet_npc.y

        # Si está en el mismo mapa, usar move_npc
        if old_map_id == map_id:
            await ctx.npc_service.move_npc(pet_npc, caster_x, caster_y, pet_npc.heading)
        elif ctx.map_manager:
            # Cambio de mapa
            ctx.map_manager.remove_npc(old_map_id, pet_npc.instance_id)

            # Actualizar posición en Redis
            await ctx.npc_repo.update_npc_position(
                pet_npc.instance_id, caster_x, caster_y, pet_npc.heading
            )

            # Actualizar posición en memoria
            pet_npc.map_id = map_id
            pet_npc.x = caster_x
            pet_npc.y = caster_y

            # Agregar al nuevo mapa
            ctx.map_manager.add_npc(map_id, pet_npc)

            # Broadcast CHARACTER_CREATE en nuevo mapa
            if ctx.broadcast_service:
                await ctx.broadcast_service.broadcast_character_create(
                    map_id=map_id,
                    char_index=pet_npc.char_index,
                    body=pet_npc.body_id,
                    head=pet_npc.head_id,
                    heading=pet_npc.heading,
                    x=caster_x,
                    y=caster_y,
                    name=pet_npc.name,
                )

        logger.info(
            "Mascota %s (%s) teletransportada de mapa %d (%d,%d) a mapa %d (%d,%d) para user_id %d",
            pet_npc.name,
            pet_npc.instance_id,
            old_map_id,
            old_x,
            old_y,
            map_id,
            caster_x,
            caster_y,
            ctx.user_id,
        )

        if ctx.message_sender:
            await ctx.message_sender.send_console_msg(f"Has invocado a {pet_npc.name}.")

        return SpellEffectResult(success=True)


class SummonEffect(SpellEffect):
    """Efecto de invocación de NPCs."""

    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si el hechizo invoca."""
        return ctx.spell_data.get("invokes", False)

    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """No aplica a NPCs."""
        return SpellEffectResult(success=False)

    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Invoca NPCs cerca del caster."""
        return await self._handle_summon(ctx)

    async def apply(self, ctx: SpellContext) -> SpellEffectResult:
        """Override para manejar invocación sin target específico."""
        return await self._handle_summon(ctx)

    async def _handle_summon(self, ctx: SpellContext) -> SpellEffectResult:
        """Maneja la invocación de NPCs."""
        if not ctx.summon_service or not ctx.player_repo or not ctx.npc_service:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(
                    "El sistema de invocación no está disponible."
                )
            return SpellEffectResult(success=False, stop_processing=True)

        npc_id = ctx.spell_data.get("npc_id", 0)
        if npc_id == 0:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg("Este hechizo no tiene NPC para invocar.")
            return SpellEffectResult(success=False, stop_processing=True)

        summon_count = ctx.spell_data.get("summon_count", 1)

        # Verificar límite de mascotas
        current_pets = await ctx.summon_service.get_player_pets(ctx.user_id)
        current_pet_count = len(current_pets) if current_pets else 0

        if current_pet_count >= MAX_PETS:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(
                    f"Ya tienes el máximo de mascotas ({MAX_PETS})."
                )
            return SpellEffectResult(success=False, stop_processing=True)

        # Limitar cantidad a invocar
        summon_count = min(summon_count, MAX_PETS - current_pet_count)
        if summon_count <= 0:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(
                    f"No puedes invocar más mascotas (máximo: {MAX_PETS})."
                )
            return SpellEffectResult(success=False, stop_processing=True)

        # Buscar posiciones de spawn cerca del target
        spawn_positions = self._find_spawn_positions(ctx.target_x, ctx.target_y, summon_count, ctx)

        if not spawn_positions:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(
                    "No hay espacio para invocar en esa posición."
                )
            return SpellEffectResult(success=False, stop_processing=True)

        # Invocar NPCs
        spawned = await self._spawn_summoned_npcs(npc_id, spawn_positions, ctx.user_id, ctx)

        if spawned > 0:
            if ctx.message_sender:
                await ctx.message_sender.send_console_msg(f"Has invocado {spawned} criatura(s).")
            logger.info(
                "user_id %d invocó %d NPCs (npc_id=%d) con hechizo %s",
                ctx.user_id,
                spawned,
                npc_id,
                ctx.spell_name,
            )
            return SpellEffectResult(success=True, stop_processing=True)

        if ctx.message_sender:
            await ctx.message_sender.send_console_msg("No se pudo invocar.")
        return SpellEffectResult(success=False, stop_processing=True)

    def _find_spawn_positions(
        self,
        center_x: int,
        center_y: int,
        count: int,
        ctx: SpellContext,
    ) -> list[tuple[int, int]]:
        """Encuentra posiciones válidas para spawn cerca del centro."""
        positions: list[tuple[int, int]] = []
        checked: set[tuple[int, int]] = set()

        # Verificar posición central primero
        if self._is_valid_spawn_position(center_x, center_y, ctx):
            positions.append((center_x, center_y))
            if len(positions) >= count:
                return positions

        # Buscar en espiral desde el centro
        for radius in range(1, 6):  # Radio máximo de 5
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if abs(dx) != radius and abs(dy) != radius:
                        continue  # Solo el borde del cuadrado

                    x = center_x + dx
                    y = center_y + dy

                    if (x, y) in checked:
                        continue
                    checked.add((x, y))

                    if self._is_valid_spawn_position(x, y, ctx):
                        positions.append((x, y))
                        if len(positions) >= count:
                            return positions

        return positions

    def _is_valid_spawn_position(self, x: int, y: int, ctx: SpellContext) -> bool:
        """Verifica si una posición es válida para spawn."""
        if x < 1 or x > MAX_COORDINATE or y < 1 or y > MAX_COORDINATE:
            return False

        if not ctx.map_manager:
            return False

        map_id = ctx.map_id

        # Verificar si está bloqueado
        if ctx.map_manager.is_blocked(map_id, x, y):
            return False

        # Verificar si hay otro NPC
        npcs = ctx.map_manager.get_npcs_in_map(map_id)
        return all(not (npc.x == x and npc.y == y) for npc in npcs)

    async def _spawn_summoned_npcs(
        self,
        npc_id: int,
        positions: list[tuple[int, int]],
        owner_user_id: int,
        ctx: SpellContext,
    ) -> int:
        """Spawnea NPCs invocados en las posiciones dadas."""
        if not ctx.npc_service or not ctx.summon_service:
            return 0

        spawned = 0

        for x, y in positions:
            npc = await ctx.npc_service.spawn_npc(
                npc_id=npc_id,
                map_id=ctx.map_id,
                x=x,
                y=y,
                owner_user_id=owner_user_id,
            )

            if npc:
                # Registrar como mascota del jugador
                await ctx.summon_service.register_pet(owner_user_id, npc.instance_id)

                # Broadcast CHARACTER_CREATE
                if ctx.broadcast_service:
                    await ctx.broadcast_service.broadcast_character_create(
                        map_id=ctx.map_id,
                        char_index=npc.char_index,
                        body=npc.body_id,
                        head=npc.head_id,
                        heading=npc.heading,
                        x=x,
                        y=y,
                        name=npc.name,
                    )

                spawned += 1

        return spawned
