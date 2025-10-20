"""Servicio de combate para PyAO Server.

Este servicio ahora actúa como fachada que coordina los componentes:
- DamageCalculator: Cálculos de daño
- RewardCalculator: Cálculos de recompensas
- CombatValidator: Validaciones de combate
- WeaponService: Stats de equipamiento
"""

import logging
from typing import TYPE_CHECKING

from src.combat_damage_calculator import DamageCalculator
from src.combat_reward_calculator import RewardCalculator
from src.combat_validator import CombatValidator
from src.combat_weapon_service import WeaponService

if TYPE_CHECKING:
    from src.equipment_repository import EquipmentRepository
    from src.inventory_repository import InventoryRepository
    from src.message_sender import MessageSender
    from src.npc import NPC
    from src.npc_repository import NPCRepository
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


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

        current_exp = stats.get("exp", 0)
        new_exp = current_exp + experience

        # Actualizar experiencia
        await self.player_repo.update_experience(user_id, new_exp)

        logger.info("Jugador %d ganó %d de experiencia (total: %d)", user_id, experience, new_exp)

        # Enviar packet de experiencia al cliente
        if message_sender:
            await message_sender.send_update_exp(new_exp)

        # TODO: Verificar si sube de nivel

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
        }
