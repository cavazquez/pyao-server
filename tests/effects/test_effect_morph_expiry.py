"""Tests para MorphExpiryEffect."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effects.effect_morph_expiry import MorphExpiryEffect


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_morphed_appearance = AsyncMock(return_value=None)
    repo.clear_morphed_appearance = AsyncMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "heading": 3})
    return repo


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager."""
    manager = MagicMock()
    manager.get_all_connected_user_ids = MagicMock(return_value=[1, 2])
    manager.get_message_sender = MagicMock(return_value=None)
    manager.get_all_message_senders_in_map = MagicMock(return_value=[])
    return manager


@pytest.fixture
def mock_account_repo() -> MagicMock:
    """Mock de AccountRepository."""
    repo = MagicMock()
    repo.get_account_by_user_id = AsyncMock(return_value={"char_race": 2, "char_head": 3})
    return repo


@pytest.mark.asyncio
async def test_apply_no_morphed_players(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
) -> None:
    """Test cuando no hay jugadores con apariencia morfeada."""
    effect = MorphExpiryEffect(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        interval_seconds=5.0,
    )

    await effect.apply(1, mock_player_repo, None)

    mock_player_repo.get_morphed_appearance.assert_called()


@pytest.mark.asyncio
async def test_apply_morph_not_expired(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
) -> None:
    """Test cuando la apariencia morfeada aún no ha expirado."""
    future_time = time.time() + 60
    mock_player_repo.get_morphed_appearance = AsyncMock(
        return_value={"morphed_until": future_time, "body": 10, "head": 11}
    )

    effect = MorphExpiryEffect(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        interval_seconds=5.0,
    )

    await effect.apply(1, mock_player_repo, None)

    mock_player_repo.clear_morphed_appearance.assert_not_called()


@pytest.mark.asyncio
async def test_apply_morph_expired(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_account_repo: MagicMock,
) -> None:
    """Test cuando la apariencia morfeada ha expirado."""
    expired_time = time.time() - 100

    # Simular que el user_id 1 tiene apariencia morfeada expirada
    async def get_morphed_side_effect(user_id: int):
        if user_id == 1:
            return {"morphed_until": expired_time, "body": 10, "head": 11}
        return None

    mock_player_repo.get_morphed_appearance = AsyncMock(side_effect=get_morphed_side_effect)

    mock_message_sender = MagicMock()
    mock_message_sender.send_character_change = AsyncMock()
    mock_map_manager.get_message_sender = MagicMock(return_value=mock_message_sender)
    mock_map_manager.get_all_message_senders_in_map = MagicMock(return_value=[])

    # Asegurar que get_all_connected_user_ids retorna [1]
    mock_map_manager.get_all_connected_user_ids = MagicMock(return_value=[1])

    # Resetear el cooldown de clase antes de crear el efecto
    MorphExpiryEffect._last_check_time = 0.0

    effect = MorphExpiryEffect(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        account_repo=mock_account_repo,
        interval_seconds=5.0,
    )

    await effect.apply(1, mock_player_repo, None)

    mock_player_repo.clear_morphed_appearance.assert_called()
    mock_message_sender.send_character_change.assert_called()


@pytest.mark.asyncio
async def test_apply_cooldown_check(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
) -> None:
    """Test que respeta el cooldown entre verificaciones."""
    effect = MorphExpiryEffect(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        interval_seconds=5.0,
    )

    # Primera llamada
    await effect.apply(1, mock_player_repo, None)
    call_count_1 = mock_player_repo.get_morphed_appearance.call_count

    # Segunda llamada inmediatamente después (debe ser ignorada por cooldown)
    await effect.apply(1, mock_player_repo, None)
    call_count_2 = mock_player_repo.get_morphed_appearance.call_count

    # Debe haber llamado la misma cantidad de veces (cooldown activo)
    assert call_count_1 == call_count_2


@pytest.mark.asyncio
async def test_get_interval_seconds() -> None:
    """Test obtener intervalo de segundos."""
    mock_player_repo = MagicMock()
    mock_map_manager = MagicMock()

    effect = MorphExpiryEffect(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        interval_seconds=10.0,
    )
    assert effect.get_interval_seconds() == 10.0


@pytest.mark.asyncio
async def test_get_name() -> None:
    """Test obtener nombre del efecto."""
    mock_player_repo = MagicMock()
    mock_map_manager = MagicMock()

    effect = MorphExpiryEffect(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
    )
    assert effect.get_name() == "MorphExpiry"
