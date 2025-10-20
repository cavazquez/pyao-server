"""Contenedor de dependencias del servidor."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.account_repository import AccountRepository
    from src.bank_repository import BankRepository
    from src.combat_service import CombatService
    from src.commerce_service import CommerceService
    from src.equipment_repository import EquipmentRepository
    from src.game_tick import GameTick
    from src.ground_items_repository import GroundItemsRepository
    from src.inventory_repository import InventoryRepository
    from src.item_catalog import ItemCatalog
    from src.loot_table_service import LootTableService
    from src.map_manager import MapManager
    from src.map_transition_service import MapTransitionService
    from src.merchant_repository import MerchantRepository
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.npc_ai_service import NPCAIService
    from src.npc_catalog import NPCCatalog
    from src.npc_repository import NPCRepository
    from src.npc_respawn_service import NPCRespawnService
    from src.npc_service import NPCService
    from src.player_map_service import PlayerMapService
    from src.player_repository import PlayerRepository
    from src.redis_client import RedisClient
    from src.server_repository import ServerRepository
    from src.spell_catalog import SpellCatalog
    from src.spell_service import SpellService
    from src.spellbook_repository import SpellbookRepository
    from src.stamina_service import StaminaService


@dataclass
class DependencyContainer:
    """Contenedor de todas las dependencias del servidor.

    Este contenedor centraliza todas las dependencias del servidor,
    facilitando la inyección de dependencias y el testing.
    """

    # Infraestructura
    redis_client: RedisClient

    # Repositorios
    player_repo: PlayerRepository
    account_repo: AccountRepository
    inventory_repo: InventoryRepository
    equipment_repo: EquipmentRepository
    merchant_repo: MerchantRepository
    bank_repo: BankRepository
    npc_repo: NPCRepository
    spellbook_repo: SpellbookRepository
    ground_items_repo: GroundItemsRepository
    server_repo: ServerRepository

    # Servicios
    combat_service: CombatService
    commerce_service: CommerceService
    spell_service: SpellService
    npc_service: NPCService
    npc_ai_service: NPCAIService
    npc_respawn_service: NPCRespawnService
    loot_table_service: LootTableService
    map_transition_service: MapTransitionService
    broadcast_service: MultiplayerBroadcastService
    stamina_service: StaminaService
    player_map_service: PlayerMapService

    # Managers
    map_manager: MapManager
    game_tick: GameTick

    # Catálogos
    npc_catalog: NPCCatalog
    spell_catalog: SpellCatalog
    item_catalog: ItemCatalog
