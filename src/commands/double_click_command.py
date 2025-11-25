"""Comando de doble click (items del inventario o NPCs)."""

from dataclasses import dataclass
from time import time

from src.commands.base import Command

# Constante para diferenciar entre slots de inventario y CharIndex de NPCs
MAX_INVENTORY_SLOT = 100


@dataclass
class DoubleClickCommand(Command):
    """Comando de doble click (solo datos).

    Attributes:
        user_id: ID del jugador que hace doble click.
        target: Target del doble click (slot de inventario si <= MAX_INVENTORY_SLOT,
            CharIndex de NPC si > MAX_INVENTORY_SLOT).
        map_id: ID del mapa donde está el jugador (necesario para buscar NPCs).
        timestamp: Timestamp del comando.
    """

    user_id: int
    target: int
    map_id: int | None = None
    timestamp: float | None = None

    def __post_init__(self) -> None:
        """Inicializa timestamp si no se proporciona."""
        if self.timestamp is None:
            self.timestamp = time()

    def is_item_click(self) -> bool:
        """Determina si el target es un item del inventario.

        Returns:
            True si target <= MAX_INVENTORY_SLOT (item), False si > MAX_INVENTORY_SLOT (NPC).
        """
        return self.target <= MAX_INVENTORY_SLOT

    def is_npc_click(self) -> bool:
        """Determina si el target es un NPC.

        Returns:
            True si target > MAX_INVENTORY_SLOT (NPC), False si <= MAX_INVENTORY_SLOT (item).
        """
        return self.target > MAX_INVENTORY_SLOT
