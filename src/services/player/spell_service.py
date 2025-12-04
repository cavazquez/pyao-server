"""Servicio de lógica de negocio para hechizos."""

from __future__ import annotations

import logging
import random
import time
from typing import TYPE_CHECKING, Any

from src.constants.gameplay import MAX_PETS
from src.game.map_manager import MAX_COORDINATE

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService

logger = logging.getLogger(__name__)

# Constantes para tipos de hechizos
SPELL_TYPE_DAMAGE = 1  # Tipo 1: Daño
SPELL_TYPE_STATUS = 2  # Tipo 2: Estados

# ID del hechizo Paralizar
SPELL_ID_PARALYZE = 9

# Duración de envenenamiento por defecto (segundos)
POISON_DURATION_SECONDS = 30.0

# Duración de inmovilización por defecto (segundos)
IMMOBILIZATION_DURATION_SECONDS = 30.0

# Duración de ceguera por defecto (segundos)
# En VB6 es IntervaloParalizado / 3 (aproximadamente 3-4 segundos)
BLINDNESS_DURATION_SECONDS = 10.0

# Duración de estupidez por defecto (segundos)
# Previene lanzar hechizos durante este tiempo
DUMBNESS_DURATION_SECONDS = 30.0

# Duración de invisibilidad por defecto (segundos)
INVISIBILITY_DURATION_SECONDS = 60.0

# Duración de mimetismo por defecto (segundos)
# En VB6 el mimetismo dura aproximadamente 5 minutos
MORPH_DURATION_SECONDS = 300.0

# ID del hechizo Mimetismo
SPELL_ID_MIMICRY = 42

# Porcentaje de HP al revivir (50%)
REVIVE_HP_PERCENTAGE = 0.5

# ID del hechizo Aturdir
SPELL_ID_STUN = 31

# IDs de hechizos de hambre
SPELL_ID_HUNGER_ATTACK = 12
SPELL_ID_IGOR_HUNGER = 13

# IDs de hechizos especiales
SPELL_ID_DRAIN = 45
SPELL_ID_WARP_PET = 46

# Reducción de hambre para hechizos (en puntos)
HUNGER_ATTACK_REDUCTION = 50  # Ataque de Hambre: reduce 50 puntos
IGOR_HUNGER_REDUCTION = 100  # Terrible hambre de Igôr: reduce 100 puntos

# Duración de buffs/debuffs de atributos (segundos)
# En VB6: buffs duran 1200 ticks, debuffs duran 700 ticks
# Convertimos a segundos (asumiendo 1 tick = 1 segundo aproximadamente)
STRENGTH_BUFF_DURATION_SECONDS = 1200.0  # 20 minutos
AGILITY_BUFF_DURATION_SECONDS = 1200.0
STRENGTH_DEBUFF_DURATION_SECONDS = 700.0  # ~11.6 minutos
AGILITY_DEBUFF_DURATION_SECONDS = 700.0

# Rango de modificadores (basado en Hechizos.dat: MinAG/MaxAG = 2-5)
MIN_ATTRIBUTE_MODIFIER = 2
MAX_ATTRIBUTE_MODIFIER = 5

# Duración de invocación (en segundos)
# En VB6 es configurable desde Server.ini (IntervaloInvocacion)
# Valor por defecto: 5 minutos (300 segundos)
SUMMON_DURATION_SECONDS = 300.0


class SpellService:
    """Servicio para gestionar la lógica de hechizos."""

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
    ) -> None:
        """Inicializa el servicio de hechizos.

        Args:
            spell_catalog: Catálogo de hechizos.
            player_repo: Repositorio de jugadores.
            npc_repo: Repositorio de NPCs.
            map_manager: Gestor de mapas.
            npc_death_service: Servicio de muerte de NPCs (opcional).
            account_repo: Repositorio de cuentas (opcional, necesario para invisibilidad).
            broadcast_service: Servicio de broadcast (opcional, necesario para invisibilidad).
            npc_service: Servicio de NPCs (opcional, necesario para invocación).
            summon_service: Servicio de invocación (opcional, necesario para invocación).
        """
        self.spell_catalog = spell_catalog
        self.player_repo = player_repo
        self.npc_repo = npc_repo
        self.map_manager = map_manager
        self.npc_death_service = npc_death_service
        self.account_repo = account_repo
        self.broadcast_service = broadcast_service
        self.npc_service = npc_service
        self.summon_service = summon_service

    async def cast_spell(  # noqa: PLR0914, PLR0915
        self,
        user_id: int,
        spell_id: int,
        target_x: int,
        target_y: int,
        message_sender: MessageSender,
    ) -> bool:
        """Lanza un hechizo.

        Nota: Este método tiene alta complejidad ciclomática y múltiples bloques
        anidados por diseño, ya que debe manejar diferentes tipos de hechizos,
        objetivos (NPCs/jugadores), y efectos (daño/curación/estados).

        Args:
            user_id: ID del jugador que lanza el hechizo.
            spell_id: ID del hechizo a lanzar.
            target_x: Coordenada X del objetivo.
            target_y: Coordenada Y del objetivo.
            message_sender: Enviador de mensajes.

        Returns:
            True si el hechizo se lanzó exitosamente, False en caso contrario.
        """
        # Obtener datos del hechizo
        spell_data = self.spell_catalog.get_spell_data(spell_id)
        if not spell_data:
            logger.warning("Hechizo %d no existe", spell_id)
            return False

        # Obtener nombre del hechizo para usar en mensajes
        spell_name = spell_data.get("name", "hechizo")

        # Verificar si el jugador está estúpido (no puede lanzar hechizos)
        dumb_until = await self.player_repo.get_dumb_until(user_id)
        current_time = time.time()
        if dumb_until > current_time:
            remaining_time = dumb_until - current_time
            logger.info(
                "user_id %d intentó lanzar hechizo pero está estúpido. "
                "Tiempo restante: %.1f segundos",
                user_id,
                remaining_time,
            )
            await message_sender.send_console_msg(
                f"No puedes lanzar hechizos. Estás aturdido (restantes: {int(remaining_time)}s)."
            )
            return False

        # Obtener stats del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            logger.warning("No se pudieron obtener stats del jugador %d", user_id)
            return False

        # Verificar mana suficiente
        mana_cost = spell_data.get("mana_cost", 0)
        current_mana = stats.get("min_mana", 0)
        if current_mana < mana_cost:
            logger.info(
                "user_id %d no tiene suficiente mana para lanzar %s: %d/%d requeridos",
                user_id,
                spell_name,
                current_mana,
                mana_cost,
            )
            await message_sender.send_console_msg("No tienes suficiente mana.")
            return False

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return False

        map_id = position["map"]

        # Buscar target en la posición (NPC o jugador)
        target_npc = None
        target_player_id: int | None = None

        # Primero buscar NPCs
        all_npcs = self.map_manager.get_npcs_in_map(map_id)
        for npc in all_npcs:
            if npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        # Si no hay NPC, buscar jugadores en esa posición
        if not target_npc:
            player_ids = self.map_manager.get_players_in_map(map_id)
            for player_id in player_ids:
                player_pos = await self.player_repo.get_position(player_id)
                if (
                    player_pos
                    and player_pos["x"] == target_x
                    and player_pos["y"] == target_y
                    and player_pos["map"] == map_id
                ):
                    target_player_id = player_id
                    break

        # Si no hay target válido, verificar si es auto-cast permitido
        if not target_npc and not target_player_id:
            spell_target = spell_data.get("target", 3)  # Default: Usuario Y NPC
            # Auto-cast permitido si: target = 1 (Usuario) o target = 3 (Usuario Y NPC)
            if spell_target in {1, 3}:  # Target = Usuario o Usuario Y NPC
                target_player_id = user_id
                logger.debug(
                    "Auto-cast activado para hechizo %s (target=%d) sobre user_id %d",
                    spell_name,
                    spell_target,
                    user_id,
                )
            else:
                await message_sender.send_console_msg("No hay objetivo válido en esa posición.")
                return False

        # Reducir mana
        stats["min_mana"] -= mana_cost
        await self.player_repo.set_stats(user_id=user_id, **stats)
        await message_sender.send_update_user_stats(**stats)

        # Verificar si es un hechizo de resucitación (debe procesarse antes de otros efectos)
        if spell_data.get("revives", False):
            # Solo puede resucitar a otros jugadores, no a uno mismo
            if target_player_id and target_player_id != user_id:
                target_player_stats = await self.player_repo.get_stats(target_player_id)
                if not target_player_stats:
                    await message_sender.send_console_msg("Objetivo inválido.")
                    return False

                current_hp = target_player_stats.get("min_hp", 0)
                max_hp = target_player_stats.get("max_hp", 100)

                # Obtener nombre del jugador objetivo
                target_player_name = (
                    self.map_manager.get_player_username(target_player_id)
                    or f"Jugador {target_player_id}"
                )

                # Verificar si el jugador está muerto (HP = 0)
                if current_hp <= 0:
                    # Revivir con HP parcial (50% por defecto)
                    revive_hp = int(max_hp * REVIVE_HP_PERCENTAGE)
                    target_player_stats["min_hp"] = revive_hp
                    await self.player_repo.set_stats(
                        user_id=target_player_id, **target_player_stats
                    )

                    # Enviar mensaje al caster
                    await message_sender.send_console_msg(f"Has resucitado a {target_player_name}.")

                    # Enviar mensaje al jugador revivido
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_user_stats(**target_player_stats)
                        await target_message_sender.send_console_msg(
                            f"{spell_name} te ha resucitado. Tienes {revive_hp}/{max_hp} HP."
                        )

                    logger.info(
                        "user_id %d resucitado por user_id %d con %s (HP: %d/%d)",
                        target_player_id,
                        user_id,
                        spell_name,
                        revive_hp,
                        max_hp,
                    )
                    return True
                # Si el jugador no está muerto, no se puede resucitar
                await message_sender.send_console_msg(f"{target_player_name} no está muerto.")
                return False
            if target_player_id == user_id:
                # No puede resucitarse a sí mismo
                await message_sender.send_console_msg("No puedes resucitarte a ti mismo.")
                return False
            # No hay target válido para resucitar
            await message_sender.send_console_msg("No hay objetivo válido para resucitar.")
            return False

        # Procesar hechizos de invocación (debe hacerse antes de otros efectos)
        if spell_data.get("invokes", False):
            return await self._handle_summon_spell(
                user_id, spell_id, spell_data, target_x, target_y, message_sender
            )

        # Obtener tipo del hechizo para usar en efectos
        spell_type = spell_data.get("type", SPELL_TYPE_DAMAGE)

        # Procesar según el tipo de target
        npc_died = False
        target_name = "objetivo"

        if target_npc:  # noqa: PLR1702
            # Target es un NPC
            target_name = target_npc.name

            # Calcular daño o curación
            min_damage = spell_data.get("min_damage", 0)
            max_damage = spell_data.get("max_damage", 0)
            base_amount = random.randint(min_damage, max_damage) if max_damage > 0 else 0

            # Bonus por inteligencia (10% por cada 10 puntos)
            intelligence_bonus = int(base_amount * (stats.get("attr_int", 0) / 100))
            total_amount = base_amount + intelligence_bonus

            # Si el hechizo cura, aplicar curación
            if spell_data.get("heals_hp", False):
                # Curación: aumentar HP sin exceder max_hp
                old_hp = target_npc.hp
                target_npc.hp = min(target_npc.hp + total_amount, target_npc.max_hp)
                healing_amount = target_npc.hp - old_hp
                npc_died = False

                # Actualizar HP en Redis
                await self.npc_repo.update_npc_hp(target_npc.instance_id, target_npc.hp)

                logger.info(
                    "NPC %s curado por %d HP (HP: %d/%d) con hechizo %s",
                    target_npc.name,
                    healing_amount,
                    target_npc.hp,
                    target_npc.max_hp,
                    spell_name,
                )
            else:
                # Daño: reducir HP
                target_npc.hp = max(0, target_npc.hp - total_amount)
                npc_died = target_npc.hp <= 0

                # Actualizar HP en Redis (si no murió)
                if not npc_died:
                    await self.npc_repo.update_npc_hp(target_npc.instance_id, target_npc.hp)

            # Remover estados del NPC ANTES de aplicar nuevos (prioridad a la curación)
            if not npc_died:
                # Curar veneno del NPC
                if spell_data.get("cures_poison", False):
                    await self.npc_repo.update_npc_poisoned_until(target_npc.instance_id, 0.0)
                    logger.info(
                        "Veneno removido de NPC %s por hechizo %s", target_npc.name, spell_name
                    )

                # Remover parálisis del NPC
                if spell_data.get("removes_paralysis", False):
                    await self.npc_repo.update_npc_paralyzed_until(target_npc.instance_id, 0.0)
                    logger.info(
                        "Parálisis removida de NPC %s por hechizo %s", target_npc.name, spell_name
                    )

            # Aplicar efectos de estado si el hechizo es tipo 2 (Estados)
            if spell_type == SPELL_TYPE_STATUS and not npc_died:
                spell_name_lower = spell_name.lower()
                if "paralizar" in spell_name_lower or spell_id == SPELL_ID_PARALYZE:
                    # Aplicar parálisis (duración: 10 segundos por defecto)
                    paralysis_duration = 10.0  # Segundos
                    paralyzed_until = time.time() + paralysis_duration
                    target_npc.paralyzed_until = paralyzed_until
                    await self.npc_repo.update_npc_paralyzed_until(
                        target_npc.instance_id, paralyzed_until
                    )
                    logger.info(
                        "NPC %s paralizado hasta %.2f (duración: %.1fs)",
                        target_npc.name,
                        paralyzed_until,
                        paralysis_duration,
                    )

            # Aplicar envenenamiento si el hechizo envenena (independiente del tipo)
            if spell_data.get("poisons", False) and not npc_died:
                poisoned_until = time.time() + POISON_DURATION_SECONDS
                target_npc.poisoned_until = poisoned_until
                target_npc.poisoned_by_user_id = user_id  # Rastrear quién envenenó
                await self.npc_repo.update_npc_poisoned_until(
                    target_npc.instance_id, poisoned_until, poisoned_by_user_id=user_id
                )
                logger.info(
                    "NPC %s envenenado hasta %.2f (duración: %.1fs) por user_id %d con hechizo %s",
                    target_npc.name,
                    poisoned_until,
                    POISON_DURATION_SECONDS,
                    user_id,
                    spell_name,
                )

            # Manejar hechizo Drenar para NPCs (transfiere HP del target al caster)
            if spell_id == SPELL_ID_DRAIN and not npc_died and total_amount > 0:
                # Obtener stats del caster
                caster_stats = await self.player_repo.get_stats(user_id)
                if caster_stats:
                    current_caster_hp = caster_stats.get("min_hp", 0)
                    max_caster_hp = caster_stats.get("max_hp", 100)

                    # Transferir HP drenado al caster (no exceder max_hp)
                    new_caster_hp = min(max_caster_hp, current_caster_hp + total_amount)
                    caster_stats["min_hp"] = new_caster_hp

                    # Guardar stats del caster
                    await self.player_repo.set_stats(user_id=user_id, **caster_stats)
                    await message_sender.send_update_user_stats(**caster_stats)

                    logger.info(
                        "user_id %d drenó %d HP de NPC %s (HP caster: %d/%d)",
                        user_id,
                        total_amount,
                        target_npc.name,
                        new_caster_hp,
                        max_caster_hp,
                    )

                    if new_caster_hp > current_caster_hp:
                        hp_gained = new_caster_hp - current_caster_hp
                        await message_sender.send_console_msg(
                            f"Has drenado {hp_gained} HP del objetivo."
                        )

        elif target_player_id:
            # Target es un jugador
            target_player_stats = await self.player_repo.get_stats(target_player_id)
            if not target_player_stats:
                await message_sender.send_console_msg("Objetivo inválido.")
                return False

            target_player_name = (
                self.map_manager.get_player_username(target_player_id)
                or f"Jugador {target_player_id}"
            )

            # Verificar si es auto-cast
            target_name = "tí mismo" if target_player_id == user_id else target_player_name

            # Calcular daño o curación
            min_damage = spell_data.get("min_damage", 0)
            max_damage = spell_data.get("max_damage", 0)
            base_amount = random.randint(min_damage, max_damage) if max_damage > 0 else 0

            # Bonus por inteligencia (10% por cada 10 puntos)
            intelligence_bonus = int(base_amount * (stats.get("attr_int", 0) / 100))
            total_amount = base_amount + intelligence_bonus

            # Si el hechizo cura, aplicar curación
            if spell_data.get("heals_hp", False):
                current_hp = target_player_stats.get("min_hp", 0)
                max_hp = target_player_stats.get("max_hp", 100)
                old_hp = current_hp
                new_hp = min(current_hp + total_amount, max_hp)
                healing_amount = new_hp - old_hp
                target_player_stats["min_hp"] = new_hp
                await self.player_repo.set_stats(user_id=target_player_id, **target_player_stats)

                # Notificar al jugador objetivo
                target_message_sender = (
                    message_sender
                    if target_player_id == user_id
                    else self.map_manager.get_player_message_sender(target_player_id)
                )
                if target_message_sender:
                    await target_message_sender.send_update_user_stats(**target_player_stats)
                    if healing_amount > 0:
                        if target_player_id == user_id:
                            await target_message_sender.send_console_msg(
                                f"Te has curado {healing_amount} HP."
                            )
                        else:
                            await target_message_sender.send_console_msg(
                                f"Te han curado {healing_amount} HP."
                            )

                logger.info(
                    "Jugador user_id %d curado por %d HP (HP: %d/%d) con hechizo %s",
                    target_player_id,
                    healing_amount,
                    new_hp,
                    max_hp,
                    spell_name,
                )
            elif min_damage > 0 or max_damage > 0:
                # Aplicar daño al jugador
                current_hp = target_player_stats.get("min_hp", 0)
                new_hp = max(0, current_hp - total_amount)
                target_player_stats["min_hp"] = new_hp
                await self.player_repo.set_stats(user_id=target_player_id, **target_player_stats)

                # Notificar al jugador objetivo (si no es auto-cast)
                if target_player_id != user_id:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_user_stats(**target_player_stats)
                        await target_message_sender.send_console_msg(
                            f"{spell_name} te ha causado {total_amount} de daño."
                        )

                # Si el jugador murió
                if new_hp <= 0:
                    logger.info(
                        "Jugador user_id %d murió por hechizo %s (daño: %d)",
                        target_player_id,
                        spell_name,
                        total_amount,
                    )

            # Remover estados ANTES de aplicar nuevos (prioridad a la curación)
            # Curar veneno
            if spell_data.get("cures_poison", False):
                await self.player_repo.update_poisoned_until(target_player_id, 0.0)
                logger.info(
                    "Veneno removido de user_id %d por hechizo %s", target_player_id, spell_name
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has curado del envenenamiento.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg(
                            "Te han curado del envenenamiento."
                        )

            # Remover parálisis/inmovilización (para jugadores es inmovilización)
            if spell_data.get("removes_paralysis", False):
                await self.player_repo.update_immobilized_until(target_player_id, 0.0)
                logger.info(
                    "Inmovilización removida de user_id %d por hechizo %s",
                    target_player_id,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has devuelto la movilidad.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg(
                            "Te han devuelto la movilidad."
                        )

            # Remover estupidez
            if spell_data.get("removes_stupidity", False):
                await self.player_repo.update_dumb_until(target_player_id, 0.0)
                logger.info(
                    "Estupidez removida de user_id %d por hechizo %s", target_player_id, spell_name
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has quitado el aturdimiento.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg(
                            "Te han quitado el aturdimiento."
                        )

            # Remover invisibilidad ANTES de aplicar nueva invisibilidad
            if spell_data.get("removes_invisibility", False):
                old_invisible_until = await self.player_repo.get_invisible_until(target_player_id)
                if old_invisible_until > time.time():
                    # El jugador está invisible, hacerlo visible
                    await self.player_repo.update_invisible_until(target_player_id, 0.0)
                    logger.info(
                        "Invisibilidad removida de user_id %d por hechizo %s",
                        target_player_id,
                        spell_name,
                    )
                    # Enviar CHARACTER_CREATE a otros jugadores
                    target_position = await self.player_repo.get_position(target_player_id)
                    if target_position and self.account_repo and self.broadcast_service:
                        map_id = target_position["map"]
                        account_data = await self.account_repo.get_account_by_user_id(
                            target_player_id
                        )
                        if account_data:
                            char_body = int(account_data.get("char_race", 1))
                            char_head = int(account_data.get("char_head", 1))
                            username = account_data.get("username", f"Player{target_player_id}")
                            if char_body == 0:
                                char_body = 1

                            # Broadcast CHARACTER_CREATE excluyendo al propio jugador
                            other_senders = self.map_manager.get_all_message_senders_in_map(
                                map_id, exclude_user_id=target_player_id
                            )
                            for other_sender in other_senders:
                                await other_sender.send_character_create(
                                    char_index=target_player_id,
                                    body=char_body,
                                    head=char_head,
                                    heading=target_position.get("heading", 3),
                                    x=target_position["x"],
                                    y=target_position["y"],
                                    name=username,
                                )
                            logger.info(
                                "user_id %d vuelto visible - CHARACTER_CREATE a %d jugadores",
                                target_player_id,
                                len(other_senders),
                            )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Ya no eres invisible.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Ya no eres invisible.")

            # Aplicar envenenamiento si el hechizo envenena
            if spell_data.get("poisons", False):
                poisoned_until = time.time() + POISON_DURATION_SECONDS
                await self.player_repo.update_poisoned_until(target_player_id, poisoned_until)
                logger.info(
                    "Jugador user_id %d envenenado hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    poisoned_until,
                    POISON_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has envenenado.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido envenenado.")

            # Aplicar inmovilización si el hechizo inmoviliza
            if spell_data.get("immobilizes", False):
                immobilized_until = time.time() + IMMOBILIZATION_DURATION_SECONDS
                await self.player_repo.update_immobilized_until(target_player_id, immobilized_until)
                logger.info(
                    "Jugador user_id %d inmovilizado hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    immobilized_until,
                    IMMOBILIZATION_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has inmovilizado.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido inmovilizado.")

            # Aplicar ceguera si el hechizo ciega
            if spell_data.get("blinds", False):
                blinded_until = time.time() + BLINDNESS_DURATION_SECONDS
                await self.player_repo.update_blinded_until(target_player_id, blinded_until)
                logger.info(
                    "Jugador user_id %d cegado hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    blinded_until,
                    BLINDNESS_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has cegado.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido cegado.")

            # Aplicar estupidez si el hechizo aturde
            if spell_data.get("dumbs", False):
                dumb_until = time.time() + DUMBNESS_DURATION_SECONDS
                await self.player_repo.update_dumb_until(target_player_id, dumb_until)
                logger.info(
                    "Jugador user_id %d aturdido hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    dumb_until,
                    DUMBNESS_DURATION_SECONDS,
                    spell_name,
                )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has aturdido.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Has sido aturdido.")

            # Aplicar invisibilidad si el hechizo hace invisible
            if spell_data.get("makes_invisible", False):
                invisible_until = time.time() + INVISIBILITY_DURATION_SECONDS
                await self.player_repo.update_invisible_until(target_player_id, invisible_until)
                logger.info(
                    "Jugador user_id %d invisible hasta %.2f (duración: %.1fs) por hechizo %s",
                    target_player_id,
                    invisible_until,
                    INVISIBILITY_DURATION_SECONDS,
                    spell_name,
                )
                # Enviar CHARACTER_REMOVE a otros jugadores
                target_position = await self.player_repo.get_position(target_player_id)
                if target_position:
                    map_id = target_position["map"]
                    # Broadcast CHARACTER_REMOVE excluyendo al propio jugador
                    other_senders = self.map_manager.get_all_message_senders_in_map(
                        map_id, exclude_user_id=target_player_id
                    )
                    for other_sender in other_senders:
                        await other_sender.send_character_remove(target_player_id)
                    logger.info(
                        "user_id %d invisible - CHARACTER_REMOVE a %d jugadores",
                        target_player_id,
                        len(other_senders),
                    )
                if target_player_id == user_id:
                    await message_sender.send_console_msg("Te has vuelto invisible.")
                else:
                    target_message_sender = self.map_manager.get_player_message_sender(
                        target_player_id
                    )
                    if target_message_sender:
                        await target_message_sender.send_console_msg("Te has vuelto invisible.")

            # Aplicar buffs/debuffs de atributos
            # Aumentar fuerza
            if spell_data.get("increases_strength", False):
                modifier_value = random.randint(MIN_ATTRIBUTE_MODIFIER, MAX_ATTRIBUTE_MODIFIER)
                expires_at = time.time() + STRENGTH_BUFF_DURATION_SECONDS
                await self.player_repo.set_strength_modifier(
                    target_player_id, expires_at, modifier_value
                )
                logger.info(
                    "user_id %d recibió buff fuerza (+%d) hasta %.2f (%.1fs) - %s",
                    target_player_id,
                    modifier_value,
                    expires_at,
                    STRENGTH_BUFF_DURATION_SECONDS,
                    spell_name,
                )
                # Obtener atributos actualizados y enviar UPDATE
                attributes = await self.player_repo.get_attributes(target_player_id)
                if attributes:
                    target_message_sender = (
                        message_sender
                        if target_player_id == user_id
                        else self.map_manager.get_player_message_sender(target_player_id)
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_strength_and_dexterity(
                            strength=attributes.get("strength", 0),
                            dexterity=attributes.get("agility", 0),
                        )

            # Reducir fuerza (debuff)
            if spell_data.get("decreases_strength", False):
                modifier_value = -random.randint(MIN_ATTRIBUTE_MODIFIER, MAX_ATTRIBUTE_MODIFIER)
                expires_at = time.time() + STRENGTH_DEBUFF_DURATION_SECONDS
                await self.player_repo.set_strength_modifier(
                    target_player_id, expires_at, modifier_value
                )
                logger.info(
                    "user_id %d recibió debuff fuerza (%d) hasta %.2f (%.1fs) - %s",
                    target_player_id,
                    modifier_value,
                    expires_at,
                    STRENGTH_DEBUFF_DURATION_SECONDS,
                    spell_name,
                )
                # Obtener atributos actualizados y enviar UPDATE
                attributes = await self.player_repo.get_attributes(target_player_id)
                if attributes:
                    target_message_sender = (
                        message_sender
                        if target_player_id == user_id
                        else self.map_manager.get_player_message_sender(target_player_id)
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_strength_and_dexterity(
                            strength=attributes.get("strength", 0),
                            dexterity=attributes.get("agility", 0),
                        )

            # Aumentar agilidad
            if spell_data.get("increases_agility", False):
                modifier_value = random.randint(MIN_ATTRIBUTE_MODIFIER, MAX_ATTRIBUTE_MODIFIER)
                expires_at = time.time() + AGILITY_BUFF_DURATION_SECONDS
                await self.player_repo.set_agility_modifier(
                    target_player_id, expires_at, modifier_value
                )
                logger.info(
                    "user_id %d recibió buff agilidad (+%d) hasta %.2f (%.1fs) - %s",
                    target_player_id,
                    modifier_value,
                    expires_at,
                    AGILITY_BUFF_DURATION_SECONDS,
                    spell_name,
                )
                # Obtener atributos actualizados y enviar UPDATE
                attributes = await self.player_repo.get_attributes(target_player_id)
                if attributes:
                    target_message_sender = (
                        message_sender
                        if target_player_id == user_id
                        else self.map_manager.get_player_message_sender(target_player_id)
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_strength_and_dexterity(
                            strength=attributes.get("strength", 0),
                            dexterity=attributes.get("agility", 0),
                        )

            # Reducir agilidad (debuff)
            if spell_data.get("decreases_agility", False):
                modifier_value = -random.randint(MIN_ATTRIBUTE_MODIFIER, MAX_ATTRIBUTE_MODIFIER)
                expires_at = time.time() + AGILITY_DEBUFF_DURATION_SECONDS
                await self.player_repo.set_agility_modifier(
                    target_player_id, expires_at, modifier_value
                )
                logger.info(
                    "user_id %d recibió debuff agilidad (%d) hasta %.2f (%.1fs) - %s",
                    target_player_id,
                    modifier_value,
                    expires_at,
                    AGILITY_DEBUFF_DURATION_SECONDS,
                    spell_name,
                )
                # Obtener atributos actualizados y enviar UPDATE
                attributes = await self.player_repo.get_attributes(target_player_id)
                if attributes:
                    target_message_sender = (
                        message_sender
                        if target_player_id == user_id
                        else self.map_manager.get_player_message_sender(target_player_id)
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_strength_and_dexterity(
                            strength=attributes.get("strength", 0),
                            dexterity=attributes.get("agility", 0),
                        )

            # Aplicar efectos de hambre si el hechizo causa hambre
            if spell_id in {SPELL_ID_HUNGER_ATTACK, SPELL_ID_IGOR_HUNGER}:
                # Obtener hambre actual del target
                hunger_thirst = await self.player_repo.get_hunger_thirst(target_player_id)
                if hunger_thirst:
                    current_hunger = hunger_thirst["min_hunger"]
                    max_hunger = hunger_thirst["max_hunger"]

                    # Determinar reducción según el hechizo
                    if spell_id == SPELL_ID_HUNGER_ATTACK:
                        hunger_reduction = HUNGER_ATTACK_REDUCTION
                    else:  # SPELL_ID_IGOR_HUNGER
                        hunger_reduction = IGOR_HUNGER_REDUCTION

                    # Reducir hambre
                    new_hunger = max(0, current_hunger - hunger_reduction)
                    hunger_flag = 1 if new_hunger <= 0 else hunger_thirst.get("hunger_flag", 0)

                    # Actualizar hambre
                    await self.player_repo.set_hunger_thirst(
                        user_id=target_player_id,
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
                    target_message_sender = (
                        message_sender
                        if target_player_id == user_id
                        else self.map_manager.get_player_message_sender(target_player_id)
                    )
                    if target_message_sender:
                        await target_message_sender.send_update_hunger_and_thirst(
                            max_water=hunger_thirst["max_water"],
                            min_water=hunger_thirst["min_water"],
                            max_hunger=max_hunger,
                            min_hunger=new_hunger,
                        )

                    logger.info(
                        "Jugador user_id %d hambre reducida en %d (de %d a %d) por hechizo %s",
                        target_player_id,
                        hunger_reduction,
                        current_hunger,
                        new_hunger,
                        spell_name,
                    )

            # Manejar hechizo Drenar (transfiere HP del target al caster)
            if (
                spell_id == SPELL_ID_DRAIN
                and min_damage > 0
                and max_damage > 0
                and total_amount > 0
            ):
                # El daño ya fue aplicado arriba, ahora transferimos HP al caster
                # Obtener stats del caster
                caster_stats = await self.player_repo.get_stats(user_id)
                if caster_stats:
                    current_caster_hp = caster_stats.get("min_hp", 0)
                    max_caster_hp = caster_stats.get("max_hp", 100)

                    # Transferir HP drenado al caster (no exceder max_hp)
                    new_caster_hp = min(max_caster_hp, current_caster_hp + total_amount)
                    caster_stats["min_hp"] = new_caster_hp

                    # Guardar stats del caster
                    await self.player_repo.set_stats(user_id=user_id, **caster_stats)
                    await message_sender.send_update_user_stats(**caster_stats)

                    logger.info(
                        "user_id %d drenó %d HP de user_id %d (HP caster: %d/%d)",
                        user_id,
                        total_amount,
                        target_player_id,
                        new_caster_hp,
                        max_caster_hp,
                    )

                    if new_caster_hp > current_caster_hp:
                        hp_gained = new_caster_hp - current_caster_hp
                        await message_sender.send_console_msg(
                            f"Has drenado {hp_gained} HP del objetivo."
                        )

            # Manejar hechizo Invocar Mascota (teletransporta mascota al caster)
            if spell_data.get("warps_pet", False):
                if self.npc_service and self.summon_service:
                    # Obtener posición del caster
                    caster_position = await self.player_repo.get_position(user_id)
                    if caster_position:
                        map_id = caster_position["map"]
                        caster_x = caster_position["x"]
                        caster_y = caster_position["y"]

                        # Obtener mascotas del jugador (lista de instance_ids)
                        player_pets = await self.summon_service.get_player_pets(user_id)

                        if player_pets and self.npc_repo:
                            # Obtener el NPC desde el instance_id
                            pet_instance_id = player_pets[0]
                            pet_npc = await self.npc_repo.get_npc(pet_instance_id)

                            if pet_npc:
                                # Guardar posición anterior
                                old_map_id = pet_npc.map_id
                                old_x = pet_npc.x
                                old_y = pet_npc.y

                                # Si está en el mismo mapa, usar move_npc
                                if old_map_id == map_id:
                                    # Mover NPC en el mismo mapa
                                    await self.npc_service.move_npc(
                                        pet_npc, caster_x, caster_y, pet_npc.heading
                                    )
                                else:
                                    # Cambio de mapa: remover del mapa anterior y agregar al nuevo
                                    self.map_manager.remove_npc(old_map_id, pet_npc.instance_id)

                                    # Actualizar posición en Redis
                                    await self.npc_repo.update_npc_position(
                                        pet_npc.instance_id, caster_x, caster_y, pet_npc.heading
                                    )

                                    # Actualizar posición en memoria
                                    pet_npc.map_id = map_id
                                    pet_npc.x = caster_x
                                    pet_npc.y = caster_y

                                    # Agregar al nuevo mapa
                                    self.map_manager.add_npc(map_id, pet_npc)

                                    # Broadcast CHARACTER_CREATE en nuevo mapa
                                    if self.broadcast_service:
                                        await self.broadcast_service.broadcast_character_create(
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
                                    (
                                        "Mascota %s (%s) teletransportada de mapa %d (%d,%d) "
                                        "a mapa %d (%d,%d) para user_id %d"
                                    ),
                                    pet_npc.name,
                                    pet_npc.instance_id,
                                    old_map_id,
                                    old_x,
                                    old_y,
                                    map_id,
                                    caster_x,
                                    caster_y,
                                    user_id,
                                )

                                await message_sender.send_console_msg(
                                    f"Has invocado a {pet_npc.name}."
                                )
                            else:
                                await message_sender.send_console_msg(
                                    "No se pudo encontrar la mascota."
                                )
                        else:
                            await message_sender.send_console_msg("No tienes mascotas invocadas.")
                else:
                    await message_sender.send_console_msg(
                        "El sistema de invocación no está disponible."
                    )

            # Manejar hechizo Mimetismo (cambiar apariencia del caster a la del target)
            if spell_data.get("morphs", False) or spell_id == SPELL_ID_MIMICRY:
                # Solo funciona sobre jugadores (no NPCs)
                if target_player_id and self.account_repo:
                    # Obtener apariencia del target
                    target_account_data = await self.account_repo.get_account_by_user_id(
                        target_player_id
                    )
                    if target_account_data:
                        target_body = int(target_account_data.get("char_race", 1))
                        target_head = int(target_account_data.get("char_head", 1))

                        # Validar body (no puede ser 0)
                        if target_body == 0:
                            target_body = 1

                        # Establecer apariencia morfeada
                        morphed_until = time.time() + MORPH_DURATION_SECONDS
                        await self.player_repo.set_morphed_appearance(
                            user_id, target_body, target_head, morphed_until
                        )

                        # Obtener posición y heading del caster
                        caster_position = await self.player_repo.get_position(user_id)
                        if caster_position:
                            map_id = caster_position["map"]
                            caster_x = caster_position["x"]
                            caster_y = caster_position["y"]
                            caster_heading = caster_position.get("heading", 3)

                            # Obtener username del caster
                            (self.map_manager.get_player_username(user_id) or f"Player{user_id}")

                            # Enviar CHARACTER_CHANGE al caster
                            await message_sender.send_character_change(
                                char_index=user_id,
                                body=target_body,
                                head=target_head,
                                heading=caster_heading,
                            )

                            # Broadcast CHARACTER_CHANGE a otros jugadores en el mapa
                            other_senders = self.map_manager.get_all_message_senders_in_map(
                                map_id, exclude_user_id=user_id
                            )
                            for sender in other_senders:
                                await sender.send_character_change(
                                    char_index=user_id,
                                    body=target_body,
                                    head=target_head,
                                    heading=caster_heading,
                                )

                            logger.debug(
                                "Mimetismo de user_id %d notificado a %d jugadores en mapa %d",
                                user_id,
                                len(other_senders),
                                map_id,
                            )

                            logger.info(
                                (
                                    "user_id %d morfeado a apariencia de user_id %d "
                                    "(body=%d head=%d) hasta %.2f"
                                ),
                                user_id,
                                target_player_id,
                                target_body,
                                target_head,
                                morphed_until,
                            )
                        else:
                            await message_sender.send_console_msg("No se pudo obtener tu posición.")
                    else:
                        await message_sender.send_console_msg(
                            "No se pudo obtener la apariencia del objetivo."
                        )
                else:
                    await message_sender.send_console_msg(
                        "El mimetismo solo funciona sobre otros jugadores."
                    )

        # Enviar mensajes según el tipo de target
        caster_msg = spell_data.get("caster_msg", "Has lanzado ")
        if target_npc:
            # Determinar si fue curación o daño
            if spell_data.get("heals_hp", False):
                # Ya se aplicó la curación, no hay total_damage
                await message_sender.send_console_msg(f"{caster_msg}{target_npc.name}.")
            else:
                # Daño aplicado - usar total_amount que está en scope
                await message_sender.send_console_msg(
                    f"{caster_msg}{target_npc.name}. Daño: {total_amount}"
                )

            # Enviar efecto visual (solo al caster por ahora, broadcast lo maneja el death service)
            fx_grh = spell_data.get("fx_grh", 0)
            loops = spell_data.get("loops", 1)
            if fx_grh > 0:
                await message_sender.send_create_fx_at_position(target_x, target_y, fx_grh, loops)

            # Log
            if spell_data.get("heals_hp", False):
                logger.info(
                    "user_id %d lanzó %s sobre NPC %s (HP: %d/%d)",
                    user_id,
                    spell_name,
                    target_npc.name,
                    target_npc.hp,
                    target_npc.max_hp,
                )
            else:
                logger.info(
                    "user_id %d lanzó %s sobre NPC %s. Daño: %d (HP restante: %d/%d)",
                    user_id,
                    spell_name,
                    target_npc.name,
                    total_amount,
                    target_npc.hp,
                    target_npc.max_hp,
                )

            # Si el NPC murió, usar servicio centralizado
            if npc_died and self.npc_death_service:
                # Calcular experiencia (similar a CombatService)
                experience = target_npc.level * 10  # 10 EXP por nivel del NPC

                # Delegar toda la lógica de muerte al servicio centralizado
                await self.npc_death_service.handle_npc_death(
                    npc=target_npc,
                    killer_user_id=user_id,
                    experience=experience,
                    message_sender=message_sender,
                    death_reason="hechizo",
                )
            elif npc_died:
                # Fallback si no hay death service
                await message_sender.send_console_msg(f"Has matado a {target_npc.name}!")
                logger.warning("NPCDeathService no disponible - NPC no fue eliminado correctamente")
        elif target_player_id:
            # Mensaje para jugador target
            if target_player_id == user_id:
                self_msg = spell_data.get("self_msg", "Te has lanzado ")
                await message_sender.send_console_msg(f"{self_msg}{spell_name}.")
            else:
                await message_sender.send_console_msg(f"{caster_msg}{target_name}.")

            # Enviar efecto visual
            fx_grh = spell_data.get("fx_grh", 0)
            loops = spell_data.get("loops", 1)
            if fx_grh > 0:
                await message_sender.send_create_fx_at_position(target_x, target_y, fx_grh, loops)

            # Log
            logger.info(
                "user_id %d lanzó %s sobre jugador %s (user_id %d)",
                user_id,
                spell_name,
                target_name,
                target_player_id,
            )

        return True

    async def _handle_summon_spell(
        self,
        user_id: int,
        spell_id: int,
        spell_data: dict[str, Any],
        target_x: int,
        target_y: int,
        message_sender: MessageSender,
    ) -> bool:
        """Maneja la lógica de invocación de hechizos.

        Args:
            user_id: ID del usuario que lanza el hechizo.
            spell_id: ID del hechizo.
            spell_data: Datos del hechizo.
            target_x: Coordenada X objetivo.
            target_y: Coordenada Y objetivo.
            message_sender: Enviador de mensajes.

        Returns:
            True si la invocación fue exitosa, False en caso contrario.
        """
        if not self.npc_service or not self.summon_service:
            await message_sender.send_console_msg("El sistema de invocación no está disponible.")
            return False

        # Obtener posición del jugador para invocar cerca
        player_position = await self.player_repo.get_position(user_id)
        if not player_position:
            await message_sender.send_console_msg("No se pudo obtener tu posición.")
            return False

        map_id = player_position["map"]
        invoke_npc_id = spell_data.get("invoke_npc_id", 0)
        invoke_count = spell_data.get("invoke_count", 1)

        if invoke_npc_id <= 0:
            await message_sender.send_console_msg("Hechizo de invocación inválido.")
            logger.warning("Hechizo de invocación sin invoke_npc_id: spell_id=%d", spell_id)
            return False

        # Validar límite de mascotas
        can_summon, error_msg = await self.summon_service.can_summon(user_id, invoke_count)
        if not can_summon:
            await message_sender.send_console_msg(error_msg)
            return False

        # Encontrar posiciones libres para invocar
        spawn_positions = self._find_spawn_positions(map_id, target_x, target_y, invoke_count)
        if len(spawn_positions) < invoke_count:
            await message_sender.send_console_msg(
                f"No hay suficiente espacio libre para invocar {invoke_count} criatura(s)."
            )
            return False

        # Invocar cada NPC
        summoned_count = await self._spawn_summoned_npcs(
            user_id, map_id, invoke_npc_id, spawn_positions[:invoke_count]
        )

        if summoned_count > 0:
            caster_msg = spell_data.get("caster_msg", "Has invocado")
            await message_sender.send_console_msg(f"{caster_msg} {summoned_count} criatura(s).")
            return True

        await message_sender.send_console_msg("No se pudo invocar ninguna criatura.")
        return False

    def _find_spawn_positions(
        self, map_id: int, center_x: int, center_y: int, count: int
    ) -> list[tuple[int, int]]:
        """Encuentra posiciones libres para invocar NPCs en espiral.

        Args:
            map_id: ID del mapa.
            center_x: Coordenada X central.
            center_y: Coordenada Y central.
            count: Número de posiciones necesarias.

        Returns:
            Lista de tuplas (x, y) con posiciones libres.
        """
        spawn_positions: list[tuple[int, int]] = []

        # Buscar posiciones libres en espiral (radio 1-3)
        for radius in range(1, 4):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    # Solo verificar el borde del radio actual
                    if radius > 1 and abs(dx) != radius and abs(dy) != radius:
                        continue

                    test_x = center_x + dx
                    test_y = center_y + dy

                    # Verificar límites del mapa
                    if (
                        test_x < 1
                        or test_x > MAX_COORDINATE
                        or test_y < 1
                        or test_y > MAX_COORDINATE
                    ):
                        continue

                    # Verificar que esté libre
                    if self.map_manager.can_move_to(map_id, test_x, test_y):
                        spawn_positions.append((test_x, test_y))
                        if len(spawn_positions) >= count:
                            return spawn_positions
        return spawn_positions

    async def _spawn_summoned_npcs(
        self,
        user_id: int,
        map_id: int,
        invoke_npc_id: int,
        spawn_positions: list[tuple[int, int]],
    ) -> int:
        """Spawnea NPCs invocados en las posiciones dadas.

        Args:
            user_id: ID del jugador que invoca.
            map_id: ID del mapa.
            invoke_npc_id: ID del NPC a invocar.
            spawn_positions: Lista de posiciones (x, y) para spawnear.

        Returns:
            Número de NPCs invocados exitosamente.
        """
        if not self.npc_service or not self.summon_service:
            return 0

        summoned_count = 0
        for spawn_x, spawn_y in spawn_positions:
            # Verificar límite antes de cada invocación
            current_pets = await self.summon_service.get_player_pets_count(user_id)
            if current_pets >= MAX_PETS:
                break

            # Spawnear NPC
            summoned_npc = await self.npc_service.spawn_npc(
                npc_id=invoke_npc_id,
                map_id=map_id,
                x=spawn_x,
                y=spawn_y,
                heading=3,  # Sur por defecto
            )

            if not summoned_npc:
                logger.error(
                    "Error al spawnear NPC invocado: npc_id=%d para user_id %d",
                    invoke_npc_id,
                    user_id,
                )
                continue

            # Configurar campos de invocación
            summoned_until = time.time() + SUMMON_DURATION_SECONDS
            await self.npc_repo.update_npc_summoned(
                summoned_npc.instance_id, user_id, summoned_until
            )
            # Actualizar el modelo NPC (ya está en memoria)
            summoned_npc.summoned_by_user_id = user_id
            summoned_npc.summoned_until = summoned_until

            # Registrar como mascota
            registered = await self.summon_service.register_pet(user_id, summoned_npc.instance_id)
            if not registered:
                logger.warning(
                    "No se pudo registrar mascota para user_id %d: instance_id=%s",
                    user_id,
                    summoned_npc.instance_id,
                )
                # Si no se pudo registrar, eliminar el NPC
                await self.npc_service.remove_npc(summoned_npc)
                continue

            summoned_count += 1
            logger.info(
                "NPC invocado: %s (npc_id=%d) para user_id %d en (%d,%d) mapa %d (expira en %.1fs)",
                summoned_npc.name,
                invoke_npc_id,
                user_id,
                spawn_x,
                spawn_y,
                map_id,
                SUMMON_DURATION_SECONDS,
            )

        return summoned_count
