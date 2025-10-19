"""Inicializador de servicios."""

import logging
from typing import TYPE_CHECKING

from src.combat_service import CombatService
from src.commerce_service import CommerceService
from src.item_catalog import ItemCatalog
from src.items_catalog import ITEMS_CATALOG
from src.loot_table_service import LootTableService
from src.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.npc_ai_service import NPCAIService
from src.npc_catalog import NPCCatalog
from src.npc_respawn_service import NPCRespawnService
from src.npc_service import NPCService
from src.spell_catalog import SpellCatalog
from src.spell_service import SpellService

if TYPE_CHECKING:
    from src.map_manager import MapManager

logger = logging.getLogger(__name__)


class ServiceInitializer:
    """Inicializa todos los servicios del servidor."""

    def __init__(self, repositories: dict, map_manager: MapManager) -> None:
        """Inicializa el inicializador de servicios.

        Args:
            repositories: Diccionario con todos los repositorios.
            map_manager: Manager de mapas ya inicializado.
        """
        self.repositories = repositories
        self.map_manager = map_manager

    async def initialize_all(self) -> dict:
        """Crea e inicializa todos los servicios.

        Returns:
            Diccionario con todos los servicios creados.
        """
        logger.info("Inicializando servicios...")

        # Catálogos
        npc_catalog = NPCCatalog()
        spell_catalog = SpellCatalog()
        item_catalog = ItemCatalog()

        # Servicio de broadcast multijugador
        broadcast_service = MultiplayerBroadcastService(
            self.map_manager,
            self.repositories["player_repo"],
            self.repositories["account_repo"],
        )
        logger.info("✓ Servicio de broadcast multijugador inicializado")

        # Servicio de NPCs
        npc_service = NPCService(
            self.repositories["npc_repo"],
            npc_catalog,
            self.map_manager,
            broadcast_service,
        )
        await npc_service.initialize_world_npcs()
        logger.info("✓ Sistema de NPCs inicializado")

        # Servicio de respawn de NPCs
        npc_respawn_service = NPCRespawnService(npc_service)
        logger.info("✓ Sistema de respawn de NPCs inicializado")

        # Servicio de loot tables
        loot_table_service = LootTableService()
        logger.info("✓ Sistema de loot tables inicializado")

        # Servicio de magia
        spell_service = SpellService(
            spell_catalog,
            self.repositories["player_repo"],
            self.repositories["npc_repo"],
            self.map_manager,
        )
        logger.info("✓ Sistema de magia inicializado")

        # Servicio de comercio
        commerce_service = CommerceService(
            self.repositories["inventory_repo"],
            self.repositories["merchant_repo"],
            ITEMS_CATALOG,
            self.repositories["player_repo"],
        )
        logger.info("✓ Servicio de comercio inicializado")

        # Servicio de combate
        combat_service = CombatService(
            self.repositories["player_repo"],
            self.repositories["npc_repo"],
            self.map_manager,
        )
        logger.info("✓ Sistema de combate inicializado")

        # Servicio de IA de NPCs
        npc_ai_service = NPCAIService(
            npc_service,
            self.map_manager,
            self.repositories["player_repo"],
        )
        logger.info("✓ Servicio de IA de NPCs inicializado")

        services = {
            "broadcast_service": broadcast_service,
            "npc_service": npc_service,
            "npc_respawn_service": npc_respawn_service,
            "loot_table_service": loot_table_service,
            "spell_service": spell_service,
            "commerce_service": commerce_service,
            "combat_service": combat_service,
            "npc_ai_service": npc_ai_service,
            "npc_catalog": npc_catalog,
            "spell_catalog": spell_catalog,
            "item_catalog": item_catalog,
        }

        logger.info("✓ %d servicios inicializados", len(services))
        return services
