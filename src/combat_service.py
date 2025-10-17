"""Servicio de combate para PyAO Server."""

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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
    ) -> None:
        """Inicializa el servicio de combate.

        Args:
            player_repo: Repositorio de jugadores.
            npc_repository: Repositorio de NPCs.
        """
        self.player_repo = player_repo
        self.npc_repository = npc_repository

    async def player_attack_npc(self, user_id: int, npc: NPC) -> dict[str, int | bool] | None:
        """Jugador ataca a un NPC.

        Args:
            user_id: ID del jugador atacante.
            npc: NPC objetivo.

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
        damage, is_critical = self._calculate_player_damage(stats, npc)

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

        # Si el NPC murió, calcular experiencia
        if npc_died:
            experience = self._calculate_experience(npc.level)
            result["experience"] = experience

            # Dar experiencia al jugador
            await self._give_experience(user_id, experience)

        return result

    def _calculate_player_damage(  # noqa: PLR6301
        self, stats: dict[str, int], npc: NPC
    ) -> tuple[int, bool]:
        """Calcula el daño que hace un jugador a un NPC.

        Args:
            stats: Stats del jugador.
            npc: NPC objetivo.

        Returns:
            Tupla (daño, es_crítico).
        """
        # Daño base del jugador (basado en fuerza)
        strength = stats.get("strength", 10)
        base_damage = strength // 2  # Fuerza / 2

        # Bonus de arma equipada (si tiene)
        # TODO: Obtener arma equipada y sumar su daño
        weapon_damage = 5  # Por ahora fijo

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

    async def _give_experience(self, user_id: int, experience: int) -> None:
        """Otorga experiencia a un jugador.

        Args:
            user_id: ID del jugador.
            experience: Cantidad de experiencia.
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

        # TODO: Verificar si sube de nivel
        # TODO: Enviar packet de experiencia al cliente

    async def npc_attack_player(self, npc: NPC, user_id: int) -> dict[str, int | bool] | None:
        """NPC ataca a un jugador.

        Args:
            npc: NPC atacante.
            user_id: ID del jugador objetivo.

        Returns:
            Diccionario con resultado del ataque:
            - damage: Daño infligido
            - player_died: Si el jugador murió
            None si el ataque falló por validaciones.
        """
        # Obtener stats del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            logger.error("No se encontraron stats para user_id %d", user_id)
            return None

        # Calcular daño
        damage = self._calculate_npc_damage(npc, stats)

        # Aplicar daño al jugador
        current_hp = stats.get("hp", 0)
        new_hp = max(0, current_hp - damage)
        player_died = new_hp <= 0

        # Actualizar HP del jugador
        await self.player_repo.update_hp(user_id, new_hp)

        logger.info(
            "NPC %s atacó a jugador %d por %d de daño (murió=%s)",
            npc.name,
            user_id,
            damage,
            player_died,
        )

        return {
            "damage": damage,
            "player_died": player_died,
        }

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
