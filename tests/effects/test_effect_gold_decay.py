"""Tests para GoldDecayEffect."""

from unittest.mock import AsyncMock

import pytest

from src.effects.effect_gold_decay import GoldDecayEffect


@pytest.fixture
def mock_server_repo() -> AsyncMock:
    """Crea un mock del ServerRepository.

    Returns:
        Mock del ServerRepository.
    """
    server_repo_mock = AsyncMock()
    # Configurar valores por defecto
    server_repo_mock.get_effect_config_float.return_value = 1.0
    return server_repo_mock


@pytest.fixture
def mock_player_repo() -> AsyncMock:
    """Crea un mock del PlayerRepository.

    Returns:
        Mock del PlayerRepository.
    """
    return AsyncMock()


def test_gold_decay_effect_initialization(mock_server_repo: AsyncMock) -> None:
    """Test que verifica la inicialización del efecto."""
    effect = GoldDecayEffect(mock_server_repo)

    assert effect.server_repo == mock_server_repo
    assert effect._counters == {}


def test_gold_decay_effect_get_interval(mock_server_repo: AsyncMock) -> None:
    """Test que verifica que el intervalo es 1 segundo."""
    effect = GoldDecayEffect(mock_server_repo)
    assert effect.get_interval_seconds() == 1.0


def test_gold_decay_effect_get_name(mock_server_repo: AsyncMock) -> None:
    """Test que verifica el nombre del efecto."""
    effect = GoldDecayEffect(mock_server_repo)
    assert effect.get_name() == "GoldDecay"


@pytest.mark.asyncio
async def test_gold_decay_effect_reduces_gold(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica la reducción de oro (1%)."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: jugador con 1000 de oro
    mock_player_repo.get_stats.return_value = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": 100,
        "min_mana": 100,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 1000,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }

    # Crear efecto con intervalo corto para testing
    mock_server_repo.get_effect_config_float.side_effect = [1.0, 0.1]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto suficientes veces para cumplir el intervalo
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se guardó con oro reducido (1% de 1000 = 10)
    mock_player_repo.set_stats.assert_called_once()
    call_kwargs = mock_player_repo.set_stats.call_args.kwargs
    assert call_kwargs["gold"] == 990  # 1000 - 10

    # Verificar que se notificó al cliente
    mock_message_sender.send_update_user_stats.assert_called_once()
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_gold_decay_effect_no_gold(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica que no se reduce oro si el jugador no tiene."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: jugador sin oro
    mock_player_repo.get_stats.return_value = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": 100,
        "min_mana": 100,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 0,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }

    mock_server_repo.get_effect_config_float.side_effect = [1.0, 0.1]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que NO se guardó (no hay oro para reducir)
    mock_player_repo.set_stats.assert_not_called()


@pytest.mark.asyncio
async def test_gold_decay_custom_percentage(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica reducción de oro con porcentaje personalizado."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: jugador con 1000 de oro
    mock_player_repo.get_stats.return_value = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": 100,
        "min_mana": 100,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 1000,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }

    # Crear efecto con 5% de reducción
    mock_server_repo.get_effect_config_float.side_effect = [5.0, 0.1]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se redujo 5% (50 de oro)
    call_kwargs = mock_player_repo.set_stats.call_args.kwargs
    assert call_kwargs["gold"] == 950  # 1000 - 50


@pytest.mark.asyncio
async def test_gold_decay_interval_not_reached(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica que no se reduce oro si no se cumplió el intervalo."""
    user_id = 1
    mock_message_sender = AsyncMock()

    mock_player_repo.get_stats.return_value = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": 100,
        "min_mana": 100,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 1000,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }

    # Intervalo largo (60 segundos)
    mock_server_repo.get_effect_config_float.side_effect = [1.0, 60.0]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto solo 1 vez (no suficiente para 60 ticks)
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que NO se guardó (intervalo no alcanzado)
    mock_player_repo.set_stats.assert_not_called()


@pytest.mark.asyncio
async def test_gold_decay_no_stats(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica el manejo cuando no hay stats del jugador."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # No hay stats
    mock_player_repo.get_stats.return_value = None

    mock_server_repo.get_effect_config_float.side_effect = [1.0, 0.1]
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que NO se guardó nada
    mock_player_repo.set_stats.assert_not_called()


def test_gold_decay_cleanup_player(mock_server_repo: AsyncMock) -> None:
    """Test que verifica la limpieza de contadores de un jugador."""
    effect = GoldDecayEffect(mock_server_repo)

    # Agregar contadores manualmente
    effect._counters[1] = 10
    effect._counters[2] = 5

    # Limpiar jugador 1
    effect.cleanup_player(1)

    # Verificar que se eliminó el jugador 1 pero no el 2
    assert 1 not in effect._counters
    assert 2 in effect._counters


@pytest.mark.asyncio
async def test_gold_decay_minimum_reduction() -> None:
    """Test que verifica que la reducción mínima es 1 oro."""
    mock_server_repo = AsyncMock()
    mock_player_repo = AsyncMock()
    mock_message_sender = AsyncMock()
    user_id = 1

    # Jugador con muy poco oro (10)
    mock_player_repo.get_stats.return_value = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": 100,
        "min_mana": 100,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 10,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }

    # 1% de 10 = 0.1, pero debe reducir mínimo 1
    mock_server_repo.get_effect_config_float.side_effect = [1.0, 0.1]
    effect = GoldDecayEffect(mock_server_repo)

    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se redujo al menos 1 oro
    call_kwargs = mock_player_repo.set_stats.call_args.kwargs
    assert call_kwargs["gold"] == 9  # 10 - 1 (mínimo)


@pytest.mark.asyncio
async def test_gold_decay_counter_increment() -> None:
    """Test que verifica que el contador se incrementa correctamente."""
    mock_server_repo = AsyncMock()
    mock_player_repo = AsyncMock()
    user_id = 1

    mock_player_repo.get_stats.return_value = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": 100,
        "min_mana": 100,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 1000,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }

    # Intervalo de 5 segundos
    mock_server_repo.get_effect_config_float.side_effect = [1.0, 5.0, 1.0, 5.0, 1.0, 5.0]
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar 3 veces
    await effect.apply(user_id, mock_player_repo, None)
    assert effect._counters[user_id] == 1

    await effect.apply(user_id, mock_player_repo, None)
    assert effect._counters[user_id] == 2

    await effect.apply(user_id, mock_player_repo, None)
    assert effect._counters[user_id] == 3
