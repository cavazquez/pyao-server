"""Calculador de daño para combate."""

import logging
import random

logger = logging.getLogger(__name__)


class DamageCalculator:
    """Calcula el daño en combate entre jugadores y NPCs.

    Esta clase encapsula todas las fórmulas de cálculo de daño,
    incluyendo críticos, defensa, y variaciones.
    """

    def __init__(
        self,
        critical_chance: float = 0.05,
        critical_multiplier: float = 1.5,
        defense_per_level: float = 0.1,
    ) -> None:
        """Inicializa el calculador de daño.

        Args:
            critical_chance: Probabilidad de crítico (default: 5%).
            critical_multiplier: Multiplicador de daño crítico (default: 1.5x).
            defense_per_level: Reducción de defensa por nivel (default: 10%).
        """
        self.critical_chance = critical_chance
        self.critical_multiplier = critical_multiplier
        self.defense_per_level = defense_per_level

    def calculate_player_damage(
        self,
        strength: int,
        weapon_damage: int,
        target_level: int,
    ) -> tuple[int, bool]:
        """Calcula el daño que hace un jugador.

        Args:
            strength: Fuerza del jugador.
            weapon_damage: Daño del arma equipada.
            target_level: Nivel del objetivo (para defensa).

        Returns:
            Tupla (daño_final, es_crítico).
        """
        # Daño base: fuerza / 2 + arma
        base_damage = (strength // 2) + weapon_damage

        # Aplicar reducción por defensa del objetivo
        damage_after_defense = self._apply_defense_reduction(base_damage, target_level)

        # Calcular crítico
        is_critical = self._roll_critical()
        if is_critical:
            damage_after_defense = int(damage_after_defense * self.critical_multiplier)

        # Asegurar daño mínimo de 1
        return max(1, damage_after_defense), is_critical

    @staticmethod
    def calculate_npc_damage(
        npc_level: int,
        armor_reduction: float = 0.1,
    ) -> int:
        """Calcula el daño que hace un NPC.

        Args:
            npc_level: Nivel del NPC atacante.
            armor_reduction: Reducción por armadura del jugador (default: 10%).

        Returns:
            Daño final.
        """
        # Daño base: nivel * 3
        base_damage = npc_level * 3

        # Variación aleatoria (±20%)
        variation = random.uniform(0.8, 1.2)  # noqa: S311
        damage = int(base_damage * variation)

        # Aplicar reducción por armadura
        damage_after_armor = int(damage * (1 - armor_reduction))

        # Asegurar daño mínimo de 1
        return max(1, damage_after_armor)

    def _apply_defense_reduction(self, damage: int, target_level: int) -> int:
        """Aplica reducción de daño por defensa del objetivo.

        Args:
            damage: Daño base.
            target_level: Nivel del objetivo.

        Returns:
            Daño después de defensa.
        """
        defense_reduction = target_level * self.defense_per_level
        damage_after_defense = int(damage * (1 - defense_reduction))
        return max(1, damage_after_defense)

    def _roll_critical(self) -> bool:
        """Determina si el ataque es crítico.

        Returns:
            True si es crítico.
        """
        return random.random() < self.critical_chance  # noqa: S311
