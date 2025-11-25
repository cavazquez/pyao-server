"""Servicios de NPCs e IA.

Ejemplo de uso:
    from src.services.npc import NPCService, NPCAIService, NPCDeathService
"""

from src.services.npc.loot_table_service import LootTableService
from src.services.npc.npc_ai_service import NPCAIService
from src.services.npc.npc_death_service import NPCDeathService
from src.services.npc.npc_respawn_service import NPCRespawnService
from src.services.npc.npc_service import NPCService

__all__ = [
    "LootTableService",
    "NPCAIService",
    "NPCDeathService",
    "NPCRespawnService",
    "NPCService",
]
