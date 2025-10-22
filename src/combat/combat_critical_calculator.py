"""Calculador de críticos y esquives para el sistema de combate."""

import random


class CriticalCalculator:
    """Calcula probabilidades de críticos y esquives en combate.

    Sistema de críticos:
    - Probabilidad base: 15%
    - Modificador por agilidad: +0.5% por cada punto de AGI sobre 10
    - Daño crítico: 2x el daño normal

    Sistema de esquives:
    - Probabilidad base: 10%
    - Modificador por agilidad: +0.7% por cada punto de AGI sobre 10
    - Esquivar anula completamente el daño
    """

    # Constantes de críticos
    BASE_CRITICAL_CHANCE = 0.15  # 15% base
    CRITICAL_DAMAGE_MULTIPLIER = 2.0  # 2x daño
    CRITICAL_AGI_MODIFIER = 0.005  # +0.5% por punto de AGI

    # Constantes de esquives
    BASE_DODGE_CHANCE = 0.10  # 10% base
    DODGE_AGI_MODIFIER = 0.007  # +0.7% por punto de AGI

    # Límites
    MAX_CRITICAL_CHANCE = 0.50  # 50% máximo
    MAX_DODGE_CHANCE = 0.40  # 40% máximo
    BASE_AGILITY = 10  # AGI base de referencia

    def calculate_critical_chance(self, agility: int) -> float:
        """Calcula la probabilidad de crítico basada en agilidad.

        Args:
            agility: Agilidad del atacante.

        Returns:
            Probabilidad de crítico (0.0 a 1.0).
        """
        # Calcular bonus por agilidad
        agi_bonus = max(0, agility - self.BASE_AGILITY) * self.CRITICAL_AGI_MODIFIER

        # Probabilidad total
        chance = self.BASE_CRITICAL_CHANCE + agi_bonus

        # Aplicar límite máximo
        return min(chance, self.MAX_CRITICAL_CHANCE)

    def calculate_dodge_chance(self, agility: int) -> float:
        """Calcula la probabilidad de esquivar basada en agilidad.

        Args:
            agility: Agilidad del defensor.

        Returns:
            Probabilidad de esquivar (0.0 a 1.0).
        """
        # Calcular bonus por agilidad
        agi_bonus = max(0, agility - self.BASE_AGILITY) * self.DODGE_AGI_MODIFIER

        # Probabilidad total
        chance = self.BASE_DODGE_CHANCE + agi_bonus

        # Aplicar límite máximo
        return min(chance, self.MAX_DODGE_CHANCE)

    def is_critical_hit(self, agility: int) -> bool:
        """Determina si un ataque es crítico.

        Args:
            agility: Agilidad del atacante.

        Returns:
            True si es crítico, False en caso contrario.
        """
        chance = self.calculate_critical_chance(agility)
        return random.random() < chance  # noqa: S311

    def is_dodged(self, agility: int) -> bool:
        """Determina si un ataque es esquivado.

        Args:
            agility: Agilidad del defensor.

        Returns:
            True si esquiva, False en caso contrario.
        """
        chance = self.calculate_dodge_chance(agility)
        return random.random() < chance  # noqa: S311

    def apply_critical_damage(self, base_damage: int) -> int:
        """Aplica el multiplicador de daño crítico.

        Args:
            base_damage: Daño base del ataque.

        Returns:
            Daño con multiplicador crítico aplicado.
        """
        return int(base_damage * self.CRITICAL_DAMAGE_MULTIPLIER)
