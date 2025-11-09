"""Tests para ServiceInitializer."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.core.service_initializer import ServiceInitializer
from src.models.item_catalog import ItemCatalog
from src.models.npc_catalog import NPCCatalog
from src.models.spell_catalog import SpellCatalog
from src.services.npc.loot_table_service import LootTableService


@pytest.fixture
def mock_repositories() -> dict:
    """Crea un diccionario con mocks de repositorios."""
    party_repo = Mock()
    party_repo.initialize = AsyncMock()
    return {
        "player_repo": Mock(),
        "account_repo": Mock(),
        "npc_repo": Mock(),
        "inventory_repo": Mock(),
        "merchant_repo": Mock(),
        "equipment_repo": Mock(),
        "party_repo": party_repo,
    }


@pytest.fixture
def mock_map_manager() -> Mock:
    """Crea un mock de MapManager."""
    return Mock()


@pytest.mark.asyncio
async def test_service_initializer_creates_all_services(
    mock_repositories: dict, mock_map_manager: Mock
) -> None:
    """Verifica que ServiceInitializer crea todos los servicios."""
    # Mock para initialize_world_npcs
    mock_npc_service = Mock()
    mock_npc_service.initialize_world_npcs = AsyncMock()

    # Mock para MapResourcesService (evita cargar 290 mapas)
    mock_map_resources_service = Mock()

    initializer = ServiceInitializer(mock_repositories, mock_map_manager)

    # Patchear servicios lentos
    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "src.core.service_initializer.NPCService", lambda *_args, **_kwargs: mock_npc_service
        )
        m.setattr(
            "src.core.service_initializer.MapResourcesService",
            lambda *_args, **_kwargs: mock_map_resources_service,
        )
        services = await initializer.initialize_all()

    # Verificar que se crearon todos los servicios
    assert "broadcast_service" in services
    assert "npc_service" in services
    assert "npc_respawn_service" in services
    assert "npc_world_manager" in services
    assert "loot_table_service" in services
    assert "spell_service" in services
    assert "commerce_service" in services
    assert "combat_service" in services
    assert "npc_ai_service" in services
    assert "npc_catalog" in services
    assert "spell_catalog" in services
    assert "item_catalog" in services

    # Verificar tipos de catálogos
    assert isinstance(services["npc_catalog"], NPCCatalog)
    assert isinstance(services["spell_catalog"], SpellCatalog)
    assert isinstance(services["item_catalog"], ItemCatalog)
    assert isinstance(services["loot_table_service"], LootTableService)


@pytest.mark.asyncio
async def test_service_initializer_returns_dict(
    mock_repositories: dict, mock_map_manager: Mock
) -> None:
    """Verifica que ServiceInitializer retorna un diccionario."""
    mock_npc_service = Mock()
    mock_npc_service.initialize_world_npcs = AsyncMock()
    mock_map_resources_service = Mock()

    initializer = ServiceInitializer(mock_repositories, mock_map_manager)

    with pytest.MonkeyPatch.context() as m:
        m.setattr(
            "src.core.service_initializer.NPCService", lambda *_args, **_kwargs: mock_npc_service
        )
        m.setattr(
            "src.core.service_initializer.MapResourcesService",
            lambda *_args, **_kwargs: mock_map_resources_service,
        )
        services = await initializer.initialize_all()

    assert isinstance(services, dict)
    assert (
        len(services) == 18
    )  # Servicios/catálogos (+1 npc_world_manager, +1 party_service, +1 door_service)
