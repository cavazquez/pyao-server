"""Tests para TaskFactory."""

from unittest.mock import Mock

import pytest

from src.core.dependency_container import DependencyContainer
from src.network.packet_id import ClientPacketID
from src.tasks.player.task_login import TaskLogin
from src.tasks.player.task_walk import TaskWalk
from src.tasks.task_factory import TaskFactory
from src.tasks.task_null import TaskNull


@pytest.fixture
def mock_deps() -> DependencyContainer:
    """Crea un DependencyContainer con mocks."""
    return DependencyContainer(
        redis_client=Mock(),
        player_repo=Mock(),
        account_repo=Mock(),
        inventory_repo=Mock(),
        equipment_repo=Mock(),
        merchant_repo=Mock(),
        bank_repo=Mock(),
        npc_repo=Mock(),
        spellbook_repo=Mock(),
        ground_items_repo=Mock(),
        server_repo=Mock(),
        clan_repo=Mock(),
        party_repo=Mock(),
        combat_service=Mock(),
        commerce_service=Mock(),
        spell_service=Mock(),
        npc_service=Mock(),
        npc_ai_service=Mock(),
        npc_death_service=Mock(),
        npc_respawn_service=Mock(),
        npc_world_manager=Mock(),
        loot_table_service=Mock(),
        map_resources_service=Mock(),
        broadcast_service=Mock(),
        stamina_service=Mock(),
        player_map_service=Mock(),
        map_manager=Mock(),
        game_tick=Mock(),
        npc_catalog=Mock(),
        spell_catalog=Mock(),
        item_catalog=Mock(),
        party_service=Mock(),
        clan_service=Mock(),
        trade_service=Mock(),
        door_repo=Mock(),
        door_service=Mock(),
        session_manager=Mock(),
        summon_service=Mock(),
    )


def test_task_factory_creation(mock_deps: DependencyContainer) -> None:
    """Verifica que TaskFactory se puede crear con dependencias."""
    factory = TaskFactory(mock_deps)
    assert factory.deps is mock_deps


def test_task_factory_creates_null_task_for_unknown_packet(mock_deps: DependencyContainer) -> None:
    """Verifica que TaskFactory crea TaskNull para packet_id desconocido."""
    factory = TaskFactory(mock_deps, enable_prevalidation=False)
    message_sender = Mock()
    session_data: dict[str, dict[str, int]] = {}

    # Usar un packet_id que no existe (255)
    task = factory.create_task(bytes([255]), message_sender, session_data)

    assert isinstance(task, TaskNull)


def test_task_factory_creates_login_task(mock_deps: DependencyContainer) -> None:
    """Verifica que TaskFactory crea TaskLogin correctamente."""
    factory = TaskFactory(mock_deps)
    message_sender = Mock()
    session_data: dict[str, dict[str, int]] = {}

    # Crear datos con packet_id de LOGIN
    data = bytes([ClientPacketID.LOGIN]) + b"\x00" * 10

    task = factory.create_task(data, message_sender, session_data)

    assert isinstance(task, TaskLogin)


def test_task_factory_creates_walk_task(mock_deps: DependencyContainer) -> None:
    """Verifica que TaskFactory crea TaskWalk correctamente."""
    factory = TaskFactory(mock_deps)
    message_sender = Mock()
    session_data: dict[str, dict[str, int]] = {}

    # Crear datos con packet_id de WALK
    data = bytes([ClientPacketID.WALK]) + b"\x01"  # dirección

    task = factory.create_task(data, message_sender, session_data)

    assert isinstance(task, TaskWalk)


def test_task_factory_creates_null_task_for_unknown_packet(mock_deps: DependencyContainer) -> None:
    """Verifica que TaskFactory crea TaskNull para packet_id desconocido."""
    factory = TaskFactory(mock_deps)
    message_sender = Mock()
    session_data: dict[str, dict[str, int]] = {}

    # Usar un packet_id que no existe (255)
    data = bytes([255]) + b"\x00" * 10

    task = factory.create_task(data, message_sender, session_data)

    assert isinstance(task, TaskNull)
