"""Tests para el sistema de tick genérico del juego."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effects.effect_gold_decay import GoldDecayEffect
from src.effects.effect_hunger_thirst import HungerThirstEffect
from src.game.game_tick import GameTick


@pytest.fixture
def mock_player_repo() -> AsyncMock:
    """Crea un mock del PlayerRepository.

    Returns:
        Mock del PlayerRepository.
    """
    return AsyncMock()


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Crea un mock del MapManager.

    Returns:
        Mock del MapManager.
    """
    return MagicMock()


@pytest.fixture
def mock_server_repo() -> AsyncMock:
    """Crea un mock del ServerRepository.

    Returns:
        Mock del ServerRepository.
    """
    server_repo_mock = AsyncMock()
    # Configurar valores por defecto
    server_repo_mock.get_effect_config_int.return_value = 4
    server_repo_mock.get_effect_config_float.return_value = 1.0
    return server_repo_mock


@pytest.fixture
def game_tick(mock_player_repo: AsyncMock, mock_map_manager: MagicMock) -> GameTick:
    """Crea una instancia de GameTick para testing.

    Returns:
        Instancia de GameTick configurada para tests.
    """
    return GameTick(
        player_repo=mock_player_repo,
        map_manager=mock_map_manager,
        tick_interval=0.1,  # Intervalo corto para tests
    )


@pytest.mark.asyncio
async def test_gold_decay_effect_reduces_gold(
    mock_player_repo: AsyncMock,
    mock_map_manager: MagicMock,  # noqa: ARG001
) -> None:
    """Test que verifica la reducción de oro (1%)."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: jugador con 1000 de oro
    mock_player_repo.get_gold = AsyncMock(return_value=1000)
    mock_player_repo.update_gold = AsyncMock()
    mock_player_repo.get_stats = AsyncMock(
        return_value={
            "max_hp": 100,
            "min_hp": 100,
            "max_mana": 100,
            "min_mana": 100,
            "max_sta": 100,
            "min_sta": 100,
            "gold": 990,
            "level": 1,
            "elu": 300,
            "experience": 0,
        }
    )

    # Crear efecto con intervalo corto para testing
    mock_server_repo = AsyncMock()
    mock_server_repo.get_effect_config_float.side_effect = [1.0, 0.1]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto suficientes veces para cumplir el intervalo
    for _ in range(1):  # 0.1 segundos / 1.0 segundo por tick = 0.1 ticks
        await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se guardó con oro reducido (1% de 1000 = 10)
    mock_player_repo.update_gold.assert_called_once_with(user_id, 990)  # 1000 - 10

    # Verificar que se notificó al cliente
    mock_message_sender.send_update_user_stats.assert_called_once()
    mock_message_sender.send_console_msg.assert_called_once()


@pytest.mark.asyncio
async def test_gold_decay_effect_no_gold(
    mock_player_repo: AsyncMock,
    mock_map_manager: MagicMock,  # noqa: ARG001
) -> None:
    """Test que verifica que no se reduce oro si el jugador no tiene."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: jugador sin oro
    mock_player_repo.get_gold = AsyncMock(return_value=0)
    mock_player_repo.update_gold = AsyncMock()

    mock_server_repo = AsyncMock()
    mock_server_repo.get_effect_config_float.side_effect = [1.0, 0.1]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que NO se guardó (no hay oro para reducir)
    mock_player_repo.update_gold.assert_not_called()


@pytest.mark.asyncio
async def test_hunger_thirst_effect_reduces_water(
    mock_player_repo: AsyncMock,
    mock_map_manager: MagicMock,  # noqa: ARG001
) -> None:
    """Test que verifica la reducción de agua."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: contador en el límite
    mock_player_repo.get_hunger_thirst.return_value = {
        "max_water": 100,
        "min_water": 80,
        "max_hunger": 100,
        "min_hunger": 90,
        "thirst_flag": 0,
        "hunger_flag": 0,
        "water_counter": 3,  # INTERVALO_SED - 1
        "hunger_counter": 0,
    }

    mock_server_repo = AsyncMock()
    mock_server_repo.get_effect_config_int.side_effect = [4, 6, 10, 10]  # intervalos y reducciones
    effect = HungerThirstEffect(mock_server_repo)

    # Aplicar el efecto (debería reducir agua)
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se guardó con agua reducida
    mock_player_repo.set_hunger_thirst.assert_called_once()
    call_kwargs = mock_player_repo.set_hunger_thirst.call_args.kwargs
    assert call_kwargs["min_water"] == 70  # 80 - 10
    assert call_kwargs["water_counter"] == 0  # Se resetea


@pytest.mark.asyncio
async def test_game_tick_applies_multiple_effects(
    game_tick: GameTick,
    mock_player_repo: AsyncMock,
    mock_map_manager: MagicMock,
) -> None:
    """Test que verifica que se aplican múltiples efectos."""
    user_id = 1
    mock_map_manager.get_all_connected_user_ids.return_value = [user_id]
    mock_message_sender = AsyncMock()
    mock_map_manager.get_message_sender.return_value = mock_message_sender

    # Configurar mocks
    mock_player_repo.get_gold = AsyncMock(return_value=1000)
    mock_player_repo.update_gold = AsyncMock()
    mock_player_repo.get_stats = AsyncMock(
        return_value={
            "max_hp": 100,
            "min_hp": 100,
            "max_mana": 100,
            "min_mana": 100,
            "max_sta": 100,
            "min_sta": 100,
            "gold": 990,
            "level": 1,
            "elu": 300,
            "experience": 0,
        }
    )

    mock_player_repo.get_hunger_thirst.return_value = {
        "max_water": 100,
        "min_water": 80,
        "max_hunger": 100,
        "min_hunger": 90,
        "thirst_flag": 0,
        "hunger_flag": 0,
        "water_counter": 0,
        "hunger_counter": 0,
    }

    # Agregar dos efectos
    mock_server_repo = AsyncMock()
    mock_server_repo.get_effect_config_int.return_value = 4
    mock_server_repo.get_effect_config_float.return_value = 1.0
    effect1 = HungerThirstEffect(mock_server_repo)
    effect2 = GoldDecayEffect(mock_server_repo)

    game_tick.add_effect(effect1)
    game_tick.add_effect(effect2)

    # Aplicar efectos manualmente (sin iniciar el loop)
    for effect in game_tick.effects:
        await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que ambos efectos se aplicaron
    assert mock_player_repo.get_hunger_thirst.called
    assert mock_player_repo.get_stats.called


@pytest.mark.asyncio
async def test_game_tick_start_and_stop(
    game_tick: GameTick,
    mock_map_manager: MagicMock,
) -> None:
    """Test que verifica el inicio y detención del sistema de tick."""
    mock_map_manager.get_all_connected_user_ids.return_value = []

    # Iniciar el tick
    game_tick.start()
    assert game_tick._running is True
    assert game_tick._task is not None

    # Esperar un poco para que el loop se ejecute
    await asyncio.sleep(0.2)

    # Detener el tick
    await game_tick.stop()
    assert game_tick._running is False
    assert game_tick._task is None


@pytest.mark.asyncio
async def test_gold_decay_custom_percentage(
    mock_player_repo: AsyncMock,
    mock_map_manager: MagicMock,  # noqa: ARG001
) -> None:
    """Test que verifica reducción de oro con porcentaje personalizado."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: jugador con 1000 de oro
    mock_player_repo.get_gold = AsyncMock(return_value=1000)
    mock_player_repo.update_gold = AsyncMock()
    mock_player_repo.get_stats = AsyncMock(
        return_value={
            "max_hp": 100,
            "min_hp": 100,
            "max_mana": 100,
            "min_mana": 100,
            "max_sta": 100,
            "min_sta": 100,
            "gold": 950,
            "level": 1,
            "elu": 300,
            "experience": 0,
        }
    )

    # Crear efecto con 5% de reducción
    mock_server_repo = AsyncMock()
    mock_server_repo.get_effect_config_float.side_effect = [5.0, 0.1]  # percentage, interval
    effect = GoldDecayEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se redujo 5% (50 de oro)
    mock_player_repo.update_gold.assert_called_once_with(user_id, 950)  # 1000 - 50


@pytest.mark.asyncio
async def test_hunger_thirst_flags_activated(
    mock_player_repo: AsyncMock,
    mock_map_manager: MagicMock,  # noqa: ARG001
) -> None:
    """Test que verifica que los flags se activan cuando llegan a 0."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: agua y hambre a punto de llegar a 0
    mock_player_repo.get_hunger_thirst.return_value = {
        "max_water": 100,
        "min_water": 5,
        "max_hunger": 100,
        "min_hunger": 5,
        "thirst_flag": 0,
        "hunger_flag": 0,
        "water_counter": 3,  # INTERVALO_SED - 1
        "hunger_counter": 5,  # INTERVALO_HAMBRE - 1
    }

    mock_server_repo = AsyncMock()
    mock_server_repo.get_effect_config_int.side_effect = [4, 6, 10, 10]  # intervalos y reducciones
    effect = HungerThirstEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que ambos flags se activaron
    call_kwargs = mock_player_repo.set_hunger_thirst.call_args.kwargs
    assert call_kwargs["min_water"] == 0
    assert call_kwargs["min_hunger"] == 0
    assert call_kwargs["thirst_flag"] == 1
    assert call_kwargs["hunger_flag"] == 1
