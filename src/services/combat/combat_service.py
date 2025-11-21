"""Servicio de combate para PyAO Server.

Este servicio ahora actúa como fachada que coordina los componentes:
- DamageCalculator: Cálculos de daño
- RewardCalculator: Cálculos de recompensas
- CombatValidator: Validaciones de combate
- WeaponService: Stats de equipamiento
"""

import logging
from typing import TYPE_CHECKING

from src.combat.combat_damage_calculator import DamageCalculator
from src.combat.combat_reward_calculator import RewardCalculator
from src.combat.combat_validator import CombatValidator
from src.config.config_manager import ConfigManager
from src.services.combat.combat_weapon_service import WeaponService
from src.utils.level_calculator import (
    calculate_level_from_experience,
    calculate_remaining_elu,
)

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)
config_manager = ConfigManager()


class CombatService:
    """Servicio para gestionar combate entre jugadores y NPCs.

    Esta clase actúa como fachada que coordina los componentes de combate.
    """

    def __init__(
        self,
        player_repo: "PlayerRepository",  # noqa: UP037
        npc_repository: "NPCRepository",  # noqa: UP037
        equipment_repo: "EquipmentRepository | None" = None,  # noqa: UP037
        inventory_repo: "InventoryRepository | None" = None,  # noqa: UP037
    ) -> None:
        """Inicializa el servicio de combate.

        Args:
            player_repo: Repositorio de jugadores.
            npc_repository: Repositorio de NPCs.
            equipment_repo: Repositorio de equipamiento (opcional).
            inventory_repo: Repositorio de inventario (opcional).
        """
        self.player_repo = player_repo
        self.npc_repository = npc_repository
        self.equipment_repo = equipment_repo
        self.inventory_repo = inventory_repo

        # Inicializar componentes
        self.damage_calculator = DamageCalculator()
        self.reward_calculator = RewardCalculator()
        self.validator = CombatValidator()

        # WeaponService solo si tenemos los repositorios necesarios
        self.weapon_service = None
        if equipment_repo and inventory_repo:
            self.weapon_service = WeaponService(equipment_repo, inventory_repo)

    async def player_attack_npc(
        self, user_id: int, npc: NPC, message_sender: MessageSender | None = None
    ) -> dict[str, int | bool] | None:
        """Jugador ataca a un NPC.

        Args:
            user_id: ID del jugador atacante.
            npc: NPC objetivo.
            message_sender: MessageSender para enviar updates al cliente.

        Returns:
            Diccionario con resultado del ataque:
            - damage: Daño infligido
            - critical: Si fue crítico
            - npc_died: Si el NPC murió
            - experience: Experiencia ganada (si murió)
            None si el ataque falló por validaciones.
        """
        # Validar que el NPC sea atacable
        if not npc.is_attackable:
            logger.warning("Intento de atacar NPC no atacable: %s", npc.name)
            return None

        # Obtener stats del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            logger.error("No se encontraron stats para user_id %d", user_id)
            return None

        # Obtener daño del arma
        weapon_damage = await self._get_weapon_damage(user_id)

        # Obtener atributos del jugador
        attributes = await self.player_repo.get_attributes(user_id)
        strength = stats.get("strength", 10)
        agility = attributes.get("agility", 10) if attributes else 10

        # Calcular agilidad del NPC (basada en nivel)
        npc_agility = npc.level * 2

        # Verificar si el NPC esquiva el ataque
        is_dodged = self.damage_calculator.critical_calculator.is_dodged(npc_agility)

        if is_dodged:
            # El NPC esquivó el ataque
            logger.info(
                "¡%s esquivó el ataque del jugador %d!",
                npc.name,
                user_id,
            )

            esquiva_resultado: dict[str, int | bool] = {
                "damage": 0,
                "critical": False,
                "dodged": True,
                "npc_died": False,
            }

            return esquiva_resultado

        # Calcular daño usando el calculador
        damage, is_critical = self.damage_calculator.calculate_player_damage(
            strength=strength,
            weapon_damage=weapon_damage,
            target_level=npc.level,
            agility=agility,
        )

        # Aplicar daño al NPC
        npc.hp -= damage
        npc_died = npc.hp <= 0

        # Actualizar HP del NPC en Redis
        if not npc_died:
            await self.npc_repository.update_npc_hp(npc.instance_id, npc.hp)
        else:
            npc.hp = 0

        # Enviar mensaje de daño al cliente
        if message_sender:
            await message_sender.send_user_hit_npc(damage)

        logger.info(
            "Jugador %d atacó a %s por %d de daño (crítico=%s, murió=%s)",
            user_id,
            npc.name,
            damage,
            is_critical,
            npc_died,
        )

        result: dict[str, int | bool] = {
            "damage": damage,
            "critical": is_critical,
            "dodged": False,
            "npc_died": npc_died,
        }

        # Si el NPC murió, calcular experiencia y loot
        if npc_died:
            experience = self.reward_calculator.calculate_experience(npc.level)
            gold = self.reward_calculator.calculate_gold_drop(npc.level)

            result["experience"] = experience
            result["gold"] = gold  # Oro para dropear en el suelo, no dar directamente

            # Dar experiencia al jugador (esto sí se da directamente)
            await self._give_experience(user_id, experience, message_sender)

            # El oro se debe dropear en el suelo, no darlo directamente
            # TODO: Crear item de oro en el tile donde murió el NPC

        return result

    async def _get_weapon_damage(self, user_id: int) -> int:
        """Obtiene el daño del arma equipada del jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Daño del arma.
        """
        if self.weapon_service:
            return await self.weapon_service.get_weapon_damage(user_id)
        return 5  # Default si no hay weapon service

    async def _give_experience(
        self, user_id: int, experience: int, message_sender: MessageSender | None = None
    ) -> None:
        """Otorga experiencia a un jugador.

        Args:
            user_id: ID del jugador.
            experience: Cantidad de experiencia.
            message_sender: MessageSender para enviar update al cliente.
        """
        # Obtener experiencia actual
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return

        current_exp = stats.get("experience", 0)
        current_level = stats.get("level", 1)
        new_exp = current_exp + experience

        # Actualizar experiencia
        await self.player_repo.update_experience(user_id, new_exp)

        logger.info("Jugador %d ganó %d de experiencia (total: %d)", user_id, experience, new_exp)

        # Enviar packet de experiencia al cliente
        if message_sender:
            await message_sender.send_update_exp(new_exp)

        # Verificar y manejar level up
        if message_sender:
            await self._check_and_handle_level_up(user_id, current_level, new_exp, message_sender)

    async def _check_and_handle_level_up(  # noqa: PLR0914
        self,
        user_id: int,
        current_level: int,
        new_experience: int,
        message_sender: MessageSender,
    ) -> None:
        """Verifica si el jugador subió de nivel y maneja el proceso completo.

        Args:
            user_id: ID del jugador.
            current_level: Nivel actual del jugador.
            new_experience: Nueva experiencia total.
            message_sender: MessageSender del jugador.
        """
        # Calcular nuevo nivel basado en experiencia
        new_level = calculate_level_from_experience(new_experience, config_manager)

        # Si no subió de nivel, solo actualizar ELU
        if new_level <= current_level:
            # Actualizar ELU restante
            remaining_elu = calculate_remaining_elu(new_experience, current_level, config_manager)
            await self.player_repo.update_level_and_elu(user_id, current_level, remaining_elu)

            # Obtener stats actuales y enviar actualización
            stats = await self.player_repo.get_stats(user_id)
            if stats:
                await message_sender.send_update_user_stats(**stats)
            return

        # El jugador subió de nivel
        logger.info(
            "¡Jugador %d subió de nivel! %d → %d",
            user_id,
            current_level,
            new_level,
        )

        # Calcular nuevo ELU
        remaining_elu = calculate_remaining_elu(new_experience, new_level, config_manager)

        # Actualizar nivel y ELU
        await self.player_repo.update_level_and_elu(user_id, new_level, remaining_elu)

        # Obtener stats actuales para actualizar
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return

        # Calcular nuevos valores de HP, Mana y Stamina basados en nivel
        # Obtener atributos para calcular stats
        attributes = await self.player_repo.get_attributes(user_id)
        if attributes:
            constitution = attributes.get("constitution", 10)
            intelligence = attributes.get("intelligence", 10)

            # Calcular nuevos máximos basados en atributos y nivel
            hp_per_con = config_manager.as_int("game.character.hp_per_con", 10)
            mana_per_int = config_manager.as_int("game.character.mana_per_int", 10)

            # HP = constitution * hp_per_con * nivel (con mínimo)
            new_max_hp = max(constitution * hp_per_con * new_level, 100)
            # Mana = intelligence * mana_per_int * nivel (con mínimo)
            new_max_mana = max(intelligence * mana_per_int * new_level, 100)
            # Stamina aumenta con nivel (base 100 + 10 por nivel)
            new_max_sta = 100 + (new_level * 10)

            # Mantener el porcentaje actual de HP/Mana/Stamina
            old_max_hp = stats.get("max_hp", 100)
            old_max_mana = stats.get("max_mana", 100)
            old_max_sta = stats.get("max_sta", 100)

            old_min_hp = stats.get("min_hp", 100)
            old_min_mana = stats.get("min_mana", 50)
            old_min_sta = stats.get("min_sta", 100)

            # Calcular nuevos valores actuales manteniendo el porcentaje
            hp_percentage = old_min_hp / old_max_hp if old_max_hp > 0 else 1.0
            mana_percentage = old_min_mana / old_max_mana if old_max_mana > 0 else 1.0
            sta_percentage = old_min_sta / old_max_sta if old_max_sta > 0 else 1.0

            new_min_hp = int(new_max_hp * hp_percentage)
            new_min_mana = int(new_max_mana * mana_percentage)
            new_min_sta = int(new_max_sta * sta_percentage)

            # Actualizar stats
            await self.player_repo.set_stats(
                user_id=user_id,
                max_hp=new_max_hp,
                min_hp=new_min_hp,
                max_mana=new_max_mana,
                min_mana=new_min_mana,
                max_sta=new_max_sta,
                min_sta=new_min_sta,
                gold=stats.get("gold", 0),
                level=new_level,
                elu=remaining_elu,
                experience=new_experience,
            )

            # Enviar actualización completa de stats
            await message_sender.send_update_user_stats(
                max_hp=new_max_hp,
                min_hp=new_min_hp,
                max_mana=new_max_mana,
                min_mana=new_min_mana,
                max_sta=new_max_sta,
                min_sta=new_min_sta,
                gold=stats.get("gold", 0),
                level=new_level,
                elu=remaining_elu,
                experience=new_experience,
            )
        else:
            # Si no hay atributos, solo actualizar nivel y ELU en stats existentes
            await self.player_repo.set_stats(
                user_id=user_id,
                max_hp=stats.get("max_hp", 100),
                min_hp=stats.get("min_hp", 100),
                max_mana=stats.get("max_mana", 100),
                min_mana=stats.get("min_mana", 50),
                max_sta=stats.get("max_sta", 100),
                min_sta=stats.get("min_sta", 100),
                gold=stats.get("gold", 0),
                level=new_level,
                elu=remaining_elu,
                experience=new_experience,
            )

            # Enviar actualización
            await message_sender.send_update_user_stats(
                max_hp=stats.get("max_hp", 100),
                min_hp=stats.get("min_hp", 100),
                max_mana=stats.get("max_mana", 100),
                min_mana=stats.get("min_mana", 50),
                max_sta=stats.get("max_sta", 100),
                min_sta=stats.get("min_sta", 100),
                gold=stats.get("gold", 0),
                level=new_level,
                elu=remaining_elu,
                experience=new_experience,
            )

        # Reproducir sonido de level up
        await message_sender.play_sound_level_up()

        # Enviar mensaje de felicitación
        await message_sender.send_console_msg(
            f"¡Felicidades! Has subido al nivel {new_level}!",
            font_color=14,  # Color dorado/amarillo para level up
        )

    def can_attack(self, attacker_pos: dict[str, int], target_pos: dict[str, int]) -> bool:
        """Verifica si un atacante puede atacar a un objetivo (rango).

        Args:
            attacker_pos: Posición del atacante (x, y).
            target_pos: Posición del objetivo (x, y).

        Returns:
            True si está en rango de ataque.
        """
        return self.validator.can_attack(attacker_pos, target_pos)

    async def npc_attack_player(
        self, npc: NPC, target_user_id: int
    ) -> dict[str, int | bool] | None:
        """NPC ataca a un jugador.

        Args:
            npc: NPC atacante.
            target_user_id: ID del jugador objetivo.

        Returns:
            Diccionario con resultado del ataque o None si falla.
            - damage: Daño infligido
            - player_died: Si el jugador murió
        """
        # Obtener stats del jugador
        player_stats = await self.player_repo.get_stats(target_user_id)
        if not player_stats:
            logger.warning("No se encontraron stats del jugador %d", target_user_id)
            return None

        # Obtener reducción de armadura
        armor_reduction = 0.1  # TODO: Obtener de WeaponService
        if self.weapon_service:
            armor_reduction = await self.weapon_service.get_armor_reduction(target_user_id)

        # Calcular daño usando el calculador
        damage = self.damage_calculator.calculate_npc_damage(
            npc_level=npc.level,
            armor_reduction=armor_reduction,
        )

        # Aplicar daño al jugador
        current_hp = player_stats.get("min_hp", 100)
        new_hp = max(0, current_hp - damage)

        await self.player_repo.update_hp(target_user_id, new_hp)

        # Verificar si el jugador murió
        player_died = new_hp <= 0

        logger.info(
            "NPC %s (nivel %d) atacó a jugador %d por %d de daño (HP: %d -> %d)",
            npc.name,
            npc.level,
            target_user_id,
            damage,
            current_hp,
            new_hp,
        )

        return {
            "damage": damage,
            "player_died": player_died,
            "new_hp": new_hp,
        }
