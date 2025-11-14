"""Calculador de críticos y esquives para el sistema de combate."""

import random

from src.config.config_manager import ConfigManager, config_manager


class CriticalCalculator:
    """Calcula probabilidades de críticos y esquives en combate.

    Sistema de críticos:
    - Probabilidad base: configurable (default 15%)
    - Modificador por agilidad: +0.5% por cada punto de AGI sobre 10
    - Daño crítico: 2x el daño normal

    Sistema de esquives:
    - Probabilidad base: configurable (default 10%)
    - Modificador por agilidad: +0.7% por cada punto de AGI sobre 10
    - Esquivar anula completamente el daño
    """

    def __init__(self) -> None:
        """Inicializa el calculador con valores de configuración."""
        # Constantes de críticos
        self.BASE_CRITICAL_CHANCE = config_manager.get("game.combat.base_critical_chance", 0.15)
        self.CRITICAL_DAMAGE_MULTIPLIER = 2.0  # 2x daño
        self.CRITICAL_AGI_MODIFIER = 0.005  # +0.5% por punto de AGI

        # Constantes de esquives
        self.BASE_DODGE_CHANCE = config_manager.get("game.combat.base_dodge_chance", 0.10)
        self.DODGE_AGI_MODIFIER = 0.007  # +0.7% por punto de AGI

        # Límites
        self.MAX_CRITICAL_CHANCE = 0.50  # 50% máximo
        self.MAX_DODGE_CHANCE = 0.40  # 40% máximo
        self.BASE_AGILITY = 10  # AGI base de referencia

    def calculate_critical_chance(self, agility: int) -> float:
        """Calcula la probabilidad de crítico basada en agilidad.

        Args:
            agility: Agilidad del atacante.

        Returns:
            Probabilidad de crítico (0.0 a 1.0).
        """
        # Calcular bonus por agilidad
        agi_bonus = max(0, agility - self.BASE_AGILITY) * ConfigManager.as_float(
            self.CRITICAL_AGI_MODIFIER
        )

        # Probabilidad total
        chance = ConfigManager.as_float(self.BASE_CRITICAL_CHANCE) + agi_bonus

        # Aplicar límite máximo
        return min(chance, ConfigManager.as_float(self.MAX_CRITICAL_CHANCE))

    def calculate_dodge_chance(self, agility: int) -> float:
        """Calcula la probabilidad de esquivar basada en agilidad.

        Args:
            agility: Agilidad del defensor.

        Returns:
            Probabilidad de esquivar (0.0 a 1.0).
        """
        # Calcular bonus por agilidad
        agi_bonus = max(0, agility - self.BASE_AGILITY) * ConfigManager.as_float(
            self.DODGE_AGI_MODIFIER
        )

        # Probabilidad total
        chance = ConfigManager.as_float(self.BASE_DODGE_CHANCE) + agi_bonus

        # Aplicar límite máximo
        return min(chance, ConfigManager.as_float(self.MAX_DODGE_CHANCE))

    def is_critical_hit(self, agility: int) -> bool:
        """Determina si un ataque es crítico.

        Args:
            agility: Agilidad del atacante.

        Returns:
            True si es crítico, False en caso contrario.
        """
        chance = self.calculate_critical_chance(agility)
        return random.random() < chance

    def is_dodged(self, agility: int) -> bool:
        """Determina si un ataque es esquivado.

        Args:
            agility: Agilidad del defensor.

        Returns:
            True si esquiva, False en caso contrario.
        """
        chance = self.calculate_dodge_chance(agility)
        return random.random() < chance

    def apply_critical_damage(self, base_damage: int) -> int:
        """Aplica el multiplicador de daño crítico.

        Args:
            base_damage: Daño base del ataque.

        Returns:
            Daño con multiplicador crítico aplicado.
        """
        return int(base_damage * self.CRITICAL_DAMAGE_MULTIPLIER)
