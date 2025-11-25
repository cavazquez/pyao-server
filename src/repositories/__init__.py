"""Package de repositories (capa de datos).

Este módulo exporta todos los repositorios principales para acceso a datos.

Ejemplo de uso:
    from src.repositories import PlayerRepository, AccountRepository
"""

from src.repositories.account_repository import AccountRepository
from src.repositories.bank_repository import BankRepository
from src.repositories.equipment_repository import EquipmentRepository
from src.repositories.ground_items_repository import GroundItemsRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.merchant_repository import MerchantRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.party_repository import PartyRepository
from src.repositories.player_repository import PlayerRepository
from src.repositories.server_repository import ServerRepository
from src.repositories.spellbook_repository import SpellbookRepository

__all__ = [
    "AccountRepository",
    "BankRepository",
    "EquipmentRepository",
    "GroundItemsRepository",
    "InventoryRepository",
    "MerchantRepository",
    "NPCRepository",
    "PartyRepository",
    "PlayerRepository",
    "ServerRepository",
    "SpellbookRepository",
]
