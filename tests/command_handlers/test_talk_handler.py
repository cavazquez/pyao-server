"""Tests para TalkCommandHandler."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.talk_handler import TalkCommandHandler
from src.commands.talk_command import TalkCommand
from src.commands.walk_command import WalkCommand
from src.models.npc import NPC


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    return repo


@pytest.fixture
def mock_account_repo() -> MagicMock:
    """Mock de AccountRepository."""
    return MagicMock()


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_all_message_senders_in_map = MagicMock(return_value=[])
    return manager


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_multiline_console_msg = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_handle_simple_message(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje simple de chat."""
    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = TalkCommand(user_id=1, message="Hola mundo")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data is not None


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test con comando inválido."""
    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
    )

    invalid_command = WalkCommand(user_id=1, heading=2)
    result = await handler.handle(invalid_command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_position(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje sin posición del jugador."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
    )

    command = TalkCommand(user_id=1, message="Hola")
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_map_manager(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje sin MapManager."""
    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=None,
        game_tick=None,
        message_sender=mock_message_sender,
    )

    command = TalkCommand(user_id=1, message="Hola")
    result = await handler.handle(command)

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_broadcast_message(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test mensaje que se broadcast a otros jugadores."""
    other_sender = MagicMock()
    other_sender.send_console_msg = AsyncMock()
    mock_map_manager.get_all_message_senders_in_map = MagicMock(
        return_value=[mock_message_sender, other_sender]
    )

    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        session_data={"username": "testuser"},
    )

    command = TalkCommand(user_id=1, message="Hola a todos")
    result = await handler.handle(command)

    assert result.success is True
    # Debe enviar a todos los jugadores
    assert other_sender.send_console_msg.called


@pytest.mark.asyncio
async def test_handle_metrics_command(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /METRICS."""
    mock_game_tick = MagicMock()
    mock_game_tick.get_metrics = MagicMock(
        return_value={
            "total_ticks": 1000,
            "avg_tick_time_ms": 5.5,
            "max_tick_time_ms": 10.0,
            "effects": {},
        }
    )
    mock_game_tick.effects = []

    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=mock_game_tick,
        message_sender=mock_message_sender,
    )

    command = TalkCommand(user_id=1, message="/METRICS")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["command"] == "metrics"
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_metrics_no_game_tick(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /METRICS sin GameTick."""
    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
    )

    command = TalkCommand(user_id=1, message="/METRICS")
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_console_msg.assert_called_once()
    assert "no disponible" in mock_message_sender.send_console_msg.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_trade_command(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /COMERCIAR."""
    mock_trade_service = MagicMock()

    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        trade_service=mock_trade_service,
    )

    command = TalkCommand(user_id=1, message="/COMERCIAR usuario")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["command"] == "trade"


@pytest.mark.asyncio
async def test_handle_trade_no_service(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /COMERCIAR sin TradeService."""
    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        trade_service=None,
    )

    command = TalkCommand(user_id=1, message="/COMERCIAR usuario")
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_console_msg.assert_called_once()
    assert "no está disponible" in mock_message_sender.send_console_msg.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_pet_command_info(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /PET INFO."""
    mock_npc_repo = MagicMock()
    mock_pet = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="pet-1",
        map_id=1,
        x=50,
        y=50,
        heading=1,
        name="Mascota",
        description="",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=False,
        is_attackable=False,
        summoned_by_user_id=1,
        summoned_until=time.time() + 300,
    )

    mock_npc_repo.get_all_npcs = AsyncMock(return_value=[mock_pet])

    mock_npc_service = MagicMock()
    mock_npc_service.npc_repository = mock_npc_repo

    mock_summon_service = MagicMock()

    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        npc_service=mock_npc_service,
        summon_service=mock_summon_service,
    )

    command = TalkCommand(user_id=1, message="/PET INFO")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["command"] == "pet"
    mock_message_sender.send_multiline_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_handle_pet_command_no_pets(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /PET sin mascotas."""
    mock_npc_repo = MagicMock()
    mock_npc_repo.get_all_npcs = AsyncMock(return_value=[])

    mock_npc_service = MagicMock()
    mock_npc_service.npc_repository = mock_npc_repo

    mock_summon_service = MagicMock()

    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        npc_service=mock_npc_service,
        summon_service=mock_summon_service,
    )

    command = TalkCommand(user_id=1, message="/PET")
    result = await handler.handle(command)

    assert result.success is True
    assert result.data["command"] == "pet"
    mock_message_sender.send_console_msg.assert_called_once()
    assert "no tienes mascotas" in mock_message_sender.send_console_msg.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_handle_pet_no_service(
    mock_player_repo: MagicMock,
    mock_account_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test comando /PET sin servicios."""
    handler = TalkCommandHandler(
        player_repo=mock_player_repo,
        account_repo=mock_account_repo,
        map_manager=mock_map_manager,
        game_tick=None,
        message_sender=mock_message_sender,
        npc_service=None,
        summon_service=None,
    )

    command = TalkCommand(user_id=1, message="/PET")
    result = await handler.handle(command)

    assert result.success is True
    mock_message_sender.send_console_msg.assert_called_once()
    assert "no está disponible" in mock_message_sender.send_console_msg.call_args[0][0].lower()
