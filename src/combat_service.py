"""Servicio de combate para PyAO Server."""

import logging
import random
from typing import TYPE_CHECKING

from src.equipment_slot import EquipmentSlot

if TYPE_CHECKING:
    from src.equipment_repository import EquipmentRepository
    from src.inventory_repository import InventoryRepository
    from src.message_sender import MessageSender
    from src.npc import NPC
    from src.npc_repository import NPCRepository
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class CombatService:
    """Servicio para gestionar combate entre jugadores y NPCs."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        npc_repository: NPCRepository,
        equipment_repo: EquipmentRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
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

        # Calcular daño
        damage, is_critical = await self._calculate_player_damage(user_id, stats, npc)

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
            experience = self._calculate_experience(npc.level)
            gold = self._calculate_gold_drop(npc.level)

            result["experience"] = experience
            result["gold"] = gold  # Oro para dropear en el suelo, no dar directamente

            # Dar experiencia al jugador (esto sí se da directamente)
            await self._give_experience(user_id, experience, message_sender)

            # El oro se debe dropear en el suelo, no darlo directamente
            # TODO: Crear item de oro en el tile donde murió el NPC

        return result

    async def _calculate_player_damage(
        self, user_id: int, stats: dict[str, int], npc: NPC
    ) -> tuple[int, bool]:
        """Calcula el daño que hace un jugador a un NPC.

        Args:
            user_id: ID del jugador.
            stats: Stats del jugador.
            npc: NPC objetivo.

        Returns:
            Tupla (daño, es_crítico).
        """
        # Daño base del jugador (basado en fuerza)
        strength = stats.get("strength", 10)
        base_damage = strength // 2  # Fuerza / 2

        # Bonus de arma equipada (si tiene)
        weapon_damage = await self._get_weapon_damage(user_id)

        # Daño total antes de defensa
        total_damage = base_damage + weapon_damage

        # Reducción por defensa del NPC (10% por nivel)
        defense_reduction = npc.level * 0.1
        damage_after_defense = int(total_damage * (1 - defense_reduction))

        # Asegurar daño mínimo de 1
        damage_after_defense = max(1, damage_after_defense)

        # Chance de crítico (5% base)
        critical_chance = 0.05  # 5%
        is_critical = random.random() < critical_chance  # noqa: S311

        if is_critical:
            damage_after_defense = int(damage_after_defense * 1.5)

        return damage_after_defense, is_critical

    async def _get_weapon_damage(self, user_id: int) -> int:
        """Obtiene el daño del arma equipada del jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Daño del arma (0 si no tiene arma equipada).
        """
        if not self.equipment_repo or not self.inventory_repo:
            return 5  # Default si no hay repositorios

        # Obtener equipamiento
        equipment = await self.equipment_repo.get_all_equipment(user_id)
        weapon_inventory_slot = equipment.get(EquipmentSlot.WEAPON)

        if not weapon_inventory_slot:
            return 2  # Daño base sin arma (puños)

        # Obtener item del inventario
        slot_data = await self.inventory_repo.get_slot(user_id, weapon_inventory_slot)
        if not slot_data:
            return 2

        # Obtener daño del item (por ahora hardcodeado, debería venir del catálogo)
        # TODO: Obtener del item catalog
        item_id, _quantity = slot_data

        # Valores temporales basados en item_id
        weapon_damages = {
            2: 15,  # Espada Larga
            3: 12,  # Hacha
            # Agregar más armas aquí
        }

        return weapon_damages.get(item_id, 5)

    def _calculate_experience(self, npc_level: int) -> int:  # noqa: PLR6301
        """Calcula la experiencia que da un NPC al morir.

        Args:
            npc_level: Nivel del NPC.

        Returns:
            Experiencia otorgada.
        """
        # Fórmula: nivel * 10 + bonus aleatorio
        base_exp = npc_level * 10
        bonus = random.randint(0, npc_level * 2)  # noqa: S311
        return base_exp + bonus

    def _calculate_gold_drop(self, npc_level: int) -> int:  # noqa: PLR6301
        """Calcula el oro que dropea un NPC al morir.

        Args:
            npc_level: Nivel del NPC.

        Returns:
            Cantidad de oro.
        """
        # Fórmula: nivel * 5 + bonus aleatorio (1-50)
        base_gold = npc_level * 5
        bonus = random.randint(1, 50)  # noqa: S311
        return base_gold + bonus

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

    def _calculate_npc_damage(  # noqa: PLR6301
        self,
        npc: NPC,
        player_stats: dict[str, int],  # noqa: ARG002
    ) -> int:
        """Calcula el daño que hace un NPC a un jugador.

        Args:
            npc: NPC atacante.
            player_stats: Stats del jugador.

        Returns:
            Daño infligido.
        """
        # Daño base del NPC (basado en nivel)
        base_damage = npc.level * 3

        # Variación aleatoria (±20%)
        variation = random.uniform(0.8, 1.2)  # noqa: S311
        damage = int(base_damage * variation)

        # Reducción por armadura del jugador
        # TODO: Obtener armadura equipada y reducir daño
        armor_reduction = 0.1  # 10% de reducción por ahora
        damage_after_armor = int(damage * (1 - armor_reduction))

        # Asegurar daño mínimo de 1
        return max(1, damage_after_armor)

    def can_attack(  # noqa: PLR6301
        self, attacker_pos: dict[str, int], target_pos: dict[str, int]
    ) -> bool:
        """Verifica si un atacante puede atacar a un objetivo (rango).

        Args:
            attacker_pos: Posición del atacante (x, y).
            target_pos: Posición del objetivo (x, y).

        Returns:
            True si está en rango de ataque (1 tile adyacente).
        """
        distance = abs(attacker_pos["x"] - target_pos["x"]) + abs(
            attacker_pos["y"] - target_pos["y"]
        )
        return distance == 1  # Solo ataque cuerpo a cuerpo por ahora

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

        # Calcular daño
        damage = self._calculate_npc_damage(npc, player_stats)

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
