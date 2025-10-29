"""Calculador de recompensas de combate."""

import logging
import random

logger = logging.getLogger(__name__)


class RewardCalculator:
    """Calcula recompensas por derrotar NPCs.

    Esta clase encapsula las fórmulas de experiencia, oro y loot.
    """

    def __init__(
        self,
        exp_per_level: int = 10,
        gold_per_level: int = 5,
    ) -> None:
        """Inicializa el calculador de recompensas.

        Args:
            exp_per_level: Experiencia base por nivel (default: 10).
            gold_per_level: Oro base por nivel (default: 5).
        """
        self.exp_per_level = exp_per_level
        self.gold_per_level = gold_per_level

    def calculate_experience(self, npc_level: int) -> int:
        """Calcula la experiencia que otorga un NPC.

        Args:
            npc_level: Nivel del NPC derrotado.

        Returns:
            Experiencia otorgada.
        """
        # Fórmula: nivel * base + bonus aleatorio
        base_exp = npc_level * self.exp_per_level
        bonus = random.randint(0, npc_level * 2)
        return base_exp + bonus

    def calculate_gold_drop(self, npc_level: int) -> int:
        """Calcula el oro que dropea un NPC.

        Args:
            npc_level: Nivel del NPC derrotado.

        Returns:
            Cantidad de oro.
        """
        # Fórmula: nivel * base + bonus aleatorio (1-50)
        base_gold = npc_level * self.gold_per_level
        bonus = random.randint(1, 50)
        return base_gold + bonus
