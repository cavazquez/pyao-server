"""Servicios de juego del servidor.

Contiene servicios para manejar la lógica de juego como
balance, combate, NPCs, etc.

Ejemplo de uso:
    from src.services.game import ClassService, BalanceService, CraftingService
"""

from src.services.game.balance_service import BalanceService
from src.services.game.class_service import ClassService
from src.services.game.crafting_service import CraftingService
from src.services.game.npc_map_spawner import NPCMapSpawner
from src.services.game.npc_service import NPCService as GameNPCService
from src.services.game.npc_spawn_service import NPCSpawnService
from src.services.game.npc_world_manager import NPCWorldManager

__all__ = [
    "BalanceService",
    "ClassService",
    "CraftingService",
    "GameNPCService",
    "NPCMapSpawner",
    "NPCSpawnService",
    "NPCWorldManager",
]
