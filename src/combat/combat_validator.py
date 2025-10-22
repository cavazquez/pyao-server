"""Validador de combate."""

import logging

logger = logging.getLogger(__name__)


class CombatValidator:
    """Valida condiciones de combate.

    Esta clase verifica rangos, línea de visión, y otras condiciones
    necesarias para que un combate sea válido.
    """

    def __init__(self, melee_range: int = 1) -> None:
        """Inicializa el validador de combate.

        Args:
            melee_range: Rango de ataque cuerpo a cuerpo (default: 1 tile).
        """
        self.melee_range = melee_range

    def can_attack(self, attacker_pos: dict[str, int], target_pos: dict[str, int]) -> bool:
        """Verifica si un atacante puede atacar a un objetivo.

        Args:
            attacker_pos: Posición del atacante (x, y).
            target_pos: Posición del objetivo (x, y).

        Returns:
            True si está en rango de ataque.
        """
        distance = CombatValidator.calculate_distance(attacker_pos, target_pos)
        return distance <= self.melee_range

    @staticmethod
    def calculate_distance(pos1: dict[str, int], pos2: dict[str, int]) -> int:
        """Calcula la distancia Manhattan entre dos posiciones.

        Args:
            pos1: Primera posición (x, y).
            pos2: Segunda posición (x, y).

        Returns:
            Distancia en tiles.
        """
        return abs(pos1["x"] - pos2["x"]) + abs(pos1["y"] - pos2["y"])

    @staticmethod
    def is_in_range(pos1: dict[str, int], pos2: dict[str, int], max_range: int) -> bool:
        """Verifica si dos posiciones están dentro de un rango.

        Args:
            pos1: Primera posición.
            pos2: Segunda posición.
            max_range: Rango máximo.

        Returns:
            True si están dentro del rango.
        """
        distance = CombatValidator.calculate_distance(pos1, pos2)
        return distance <= max_range
