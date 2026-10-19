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
from src.services.combat.physical_plan import (
    PhysicalPlan,
    PhysicalRequest,
    commit_physical,
    defend_npc,
)
from src.services.player.lifecycle import apply_player_damage
from src.services.player_progression import publish_progress
from src.utils.gold_atomic import operation_id

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
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
        item_catalog: "ItemCatalog | None" = None,  # noqa: UP037
    ) -> None:
        """Inicializa el servicio de combate.

        Args:
            player_repo: Repositorio de jugadores.
            npc_repository: Repositorio de NPCs.
            equipment_repo: Repositorio de equipamiento (opcional).
            inventory_repo: Repositorio de inventario (opcional).
            item_catalog: Catálogo de items para stats de armas/armaduras (opcional).
        """
        self.player_repo = player_repo
        self.npc_repository = npc_repository
        self.equipment_repo = equipment_repo
        self.inventory_repo = inventory_repo
        self.item_catalog = item_catalog

        # Inicializar componentes
        self.damage_calculator = DamageCalculator()
        self.reward_calculator = RewardCalculator()
        self.validator = CombatValidator()

        # WeaponService solo si tenemos los repositorios necesarios
        self.weapon_service = None
        if equipment_repo and inventory_repo:
            self.weapon_service = WeaponService(equipment_repo, inventory_repo, item_catalog)

    async def player_attack_npc(
        self,
        user_id: int,
        npc: NPC,
        message_sender: MessageSender | None = None,
        *,
        defer_rewards: bool = False,
    ) -> dict[str, int | bool] | None:
        """Jugador ataca a un NPC.

        Args:
            user_id: ID del jugador atacante.
            npc: NPC objetivo.
            message_sender: MessageSender para enviar updates al cliente.
            defer_rewards: El servicio de muerte liquidará la recompensa una sola vez.

        Returns:
            Diccionario con resultado del ataque:
            - damage: Daño infligido
            - critical: Si fue crítico
            - npc_died: Si el NPC murió
            - experience: Experiencia ganada (si murió)
            None si el ataque falló por validaciones.
        """
        if self.inventory_repo is not None and self.item_catalog is not None:
            plan = PhysicalPlan(
                PhysicalRequest(user_id, target_npc=npc.instance_id),
                self.item_catalog,
                self.inventory_repo.MAX_SLOTS,
                self.inventory_repo.stacking.max_stack,
            )
            result = await commit_physical(self.player_repo.redis.redis, plan, operation_id())
            if not result.get("applied"):
                return None
            npc.hp = int(result["new_hp"])
            if result.get("npc_died"):
                result["experience"] = self.reward_calculator.calculate_experience(npc.level)
                result["gold"] = self.reward_calculator.calculate_gold_drop(npc.level)
                if not defer_rewards:
                    await self._give_experience(user_id, int(result["experience"]), message_sender)
            if message_sender:
                await message_sender.send_user_hit_npc(int(result["damage"]))
                await publish_progress(self.player_repo, user_id, message_sender)
            return result

        # Validar que el NPC sea atacable
        if not npc.is_attackable:
            logger.warning("Intento de atacar NPC no atacable: %s", npc.name)
            return None

        # Obtener atributos del jugador (strength y agility están en attributes)
        attributes = await self.player_repo.get_player_attributes(user_id)
        if not attributes:
            logger.error("No se encontraron atributos para user_id %d", user_id)
            return None

        strength = attributes.strength
        agility = attributes.agility

        # Obtener daño del arma
        weapon_damage = await self._get_weapon_damage(user_id)

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

        result = {
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
            result["gold"] = gold  # Oro para dropear en el suelo (manejado por NPCDeathService)

            # El flujo de producción usa NPCDeathService para solo/party. El
            # fallback sin ese servicio conserva el otorgamiento directo.
            if not defer_rewards:
                await self._give_experience(user_id, experience, message_sender)

            # Nota: El drop de oro lo maneja NPCDeathService.handle_npc_death()
            # cuando attack_handler llama a ese servicio

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
        experience_data = await self.player_repo.get_experience(user_id)
        current_exp = experience_data[0]
        current_level = await self.player_repo.get_level(user_id)
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

    async def _check_and_handle_level_up(
        self,
        user_id: int,
        _current_level: int,
        _new_experience: int,
        message_sender: MessageSender,
    ) -> None:
        """Confirma crecimiento y puntos desde el estado Redis más reciente."""
        from src.services.player_progression import advance_player_level  # noqa: PLC0415

        await advance_player_level(self.player_repo, user_id, message_sender)

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
        if self.item_catalog is not None:
            raw_damage = self.damage_calculator.calculate_npc_damage(
                npc_level=npc.level, armor_reduction=0.0
            )
            return await defend_npc(
                self.player_repo.redis.redis,
                target_user_id,
                npc.instance_id,
                self.item_catalog,
                raw_damage,
                operation_id(),
            )

        # Obtener stats del jugador
        player_stats = await self.player_repo.get_player_stats(target_user_id)
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

        current_hp = await self.player_repo.get_current_hp(target_user_id)
        result = await apply_player_damage(
            self.player_repo.redis.redis, target_user_id, damage, operation_id()
        )
        new_hp, player_died = int(result["new_hp"]), bool(result["player_died"])

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
            "life_id": result["life_id"],
        }
