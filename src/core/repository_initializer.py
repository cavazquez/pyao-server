"""Inicializador de repositorios."""

import logging
from typing import TYPE_CHECKING, Any

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

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class RepositoryInitializer:
    """Inicializa todos los repositorios del servidor."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el inicializador de repositorios.

        Args:
            redis_client: Cliente de Redis ya conectado.
        """
        self.redis_client = redis_client

    def initialize_all(self) -> dict[str, Any]:
        """Crea e inicializa todos los repositorios.

        Returns:
            Diccionario con todos los repositorios creados.
        """
        logger.info("Inicializando repositorios...")

        repositories = {
            "player_repo": PlayerRepository(self.redis_client),
            "account_repo": AccountRepository(self.redis_client),
            "server_repo": ServerRepository(self.redis_client),
            "inventory_repo": InventoryRepository(self.redis_client),
            "equipment_repo": EquipmentRepository(self.redis_client),
            "merchant_repo": MerchantRepository(self.redis_client),
            "bank_repo": BankRepository(self.redis_client),
            "npc_repo": NPCRepository(self.redis_client),
            "party_repo": PartyRepository(self.redis_client),
            "spellbook_repo": SpellbookRepository(self.redis_client),
            "ground_items_repo": GroundItemsRepository(self.redis_client),
        }

        logger.info("✓ %d repositorios inicializados", len(repositories))
        return repositories
