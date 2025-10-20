"""Tests para ServiceInitializer."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.item_catalog import ItemCatalog
from src.loot_table_service import LootTableService
from src.npc_catalog import NPCCatalog
from src.service_initializer import ServiceInitializer
from src.spell_catalog import SpellCatalog


@pytest.fixture
def mock_repositories() -> dict:
    """Crea un diccionario con mocks de repositorios."""
    return {
        "player_repo": Mock(),
        "account_repo": Mock(),
        "npc_repo": Mock(),
        "inventory_repo": Mock(),
        "merchant_repo": Mock(),
        "equipment_repo": Mock(),
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

    initializer = ServiceInitializer(mock_repositories, mock_map_manager)

    # Patchear NPCService para que retorne nuestro mock
    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.service_initializer.NPCService", lambda *_args, **_kwargs: mock_npc_service)
        services = await initializer.initialize_all()

    # Verificar que se crearon todos los servicios
    assert "broadcast_service" in services
    assert "npc_service" in services
    assert "npc_respawn_service" in services
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

    initializer = ServiceInitializer(mock_repositories, mock_map_manager)

    with pytest.MonkeyPatch.context() as m:
        m.setattr("src.service_initializer.NPCService", lambda *_args, **_kwargs: mock_npc_service)
        services = await initializer.initialize_all()

    assert isinstance(services, dict)
    assert len(services) == 13  # 13 servicios/catálogos (agregado stamina_service)
