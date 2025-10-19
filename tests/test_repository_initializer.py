"""Tests para RepositoryInitializer."""

from unittest.mock import Mock

from src.account_repository import AccountRepository
from src.bank_repository import BankRepository
from src.equipment_repository import EquipmentRepository
from src.ground_items_repository import GroundItemsRepository
from src.inventory_repository import InventoryRepository
from src.merchant_repository import MerchantRepository
from src.npc_repository import NPCRepository
from src.player_repository import PlayerRepository
from src.repository_initializer import RepositoryInitializer
from src.server_repository import ServerRepository
from src.spellbook_repository import SpellbookRepository


def test_repository_initializer_creates_all_repositories() -> None:
    """Verifica que RepositoryInitializer crea todos los repositorios."""
    redis_client = Mock()
    initializer = RepositoryInitializer(redis_client)

    repositories = initializer.initialize_all()

    # Verificar que se crearon todos los repositorios
    assert "player_repo" in repositories
    assert "account_repo" in repositories
    assert "server_repo" in repositories
    assert "inventory_repo" in repositories
    assert "equipment_repo" in repositories
    assert "merchant_repo" in repositories
    assert "bank_repo" in repositories
    assert "npc_repo" in repositories
    assert "spellbook_repo" in repositories
    assert "ground_items_repo" in repositories

    # Verificar tipos
    assert isinstance(repositories["player_repo"], PlayerRepository)
    assert isinstance(repositories["account_repo"], AccountRepository)
    assert isinstance(repositories["server_repo"], ServerRepository)
    assert isinstance(repositories["inventory_repo"], InventoryRepository)
    assert isinstance(repositories["equipment_repo"], EquipmentRepository)
    assert isinstance(repositories["merchant_repo"], MerchantRepository)
    assert isinstance(repositories["bank_repo"], BankRepository)
    assert isinstance(repositories["npc_repo"], NPCRepository)
    assert isinstance(repositories["spellbook_repo"], SpellbookRepository)
    assert isinstance(repositories["ground_items_repo"], GroundItemsRepository)

    # Los repositorios fueron creados correctamente (no podemos verificar redis_client interno)


def test_repository_initializer_returns_dict() -> None:
    """Verifica que RepositoryInitializer retorna un diccionario."""
    redis_client = Mock()
    initializer = RepositoryInitializer(redis_client)

    repositories = initializer.initialize_all()

    assert isinstance(repositories, dict)
    assert len(repositories) == 10  # 10 repositorios
