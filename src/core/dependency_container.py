"""Contenedor de dependencias del servidor."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.game_tick import GameTick
    from src.game.map_manager import MapManager
    from src.models.item_catalog import ItemCatalog
    from src.models.npc_catalog import NPCCatalog
    from src.models.spell_catalog import SpellCatalog
    from src.network.session_manager import SessionManager
    from src.repositories.account_repository import AccountRepository
    from src.repositories.bank_repository import BankRepository
    from src.repositories.clan_repository import ClanRepository
    from src.repositories.door_repository import DoorRepository
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.ground_items_repository import GroundItemsRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.merchant_repository import MerchantRepository
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.party_repository import PartyRepository
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository
    from src.repositories.spellbook_repository import SpellbookRepository
    from src.services.clan_service import ClanService
    from src.services.combat.combat_service import CombatService
    from src.services.commerce_service import CommerceService
    from src.services.game.npc_world_manager import NPCWorldManager
    from src.services.map.door_service import DoorService
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.map.player_map_service import PlayerMapService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.loot_table_service import LootTableService
    from src.services.npc.npc_ai_service import NPCAIService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_respawn_service import NPCRespawnService
    from src.services.npc.npc_service import NPCService
    from src.services.party_service import PartyService
    from src.services.player.spell_service import SpellService
    from src.services.player.stamina_service import StaminaService
    from src.services.trade_service import TradeService
    from src.utils.redis_client import RedisClient


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
    door_repo: DoorRepository
    npc_repo: NPCRepository
    clan_repo: ClanRepository
    party_repo: PartyRepository
    spellbook_repo: SpellbookRepository
    ground_items_repo: GroundItemsRepository
    server_repo: ServerRepository

    # Servicios
    combat_service: CombatService
    commerce_service: CommerceService
    spell_service: SpellService
    npc_service: NPCService
    npc_ai_service: NPCAIService
    npc_death_service: NPCDeathService
    npc_respawn_service: NPCRespawnService
    npc_world_manager: NPCWorldManager
    loot_table_service: LootTableService
    map_resources_service: MapResourcesService
    door_service: DoorService
    broadcast_service: MultiplayerBroadcastService
    stamina_service: StaminaService
    player_map_service: PlayerMapService
    party_service: PartyService
    clan_service: ClanService
    trade_service: TradeService

    # Managers
    map_manager: MapManager
    game_tick: GameTick
    session_manager: SessionManager

    # Catálogos
    npc_catalog: NPCCatalog
    spell_catalog: SpellCatalog
    item_catalog: ItemCatalog
