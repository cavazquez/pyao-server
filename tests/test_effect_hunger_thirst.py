"""Tests para HungerThirstEffect."""

from unittest.mock import AsyncMock

import pytest

from src.effects.effect_hunger_thirst import HungerThirstEffect


@pytest.fixture
def mock_server_repo() -> AsyncMock:
    """Crea un mock del ServerRepository.

    Returns:
        Mock del ServerRepository.
    """
    server_repo_mock = AsyncMock()
    # Configurar valores por defecto
    server_repo_mock.get_effect_config_int.return_value = 4
    return server_repo_mock


@pytest.fixture
def mock_player_repo() -> AsyncMock:
    """Crea un mock del PlayerRepository.

    Returns:
        Mock del PlayerRepository.
    """
    return AsyncMock()


def test_hunger_thirst_effect_initialization(mock_server_repo: AsyncMock) -> None:
    """Test que verifica la inicialización del efecto."""
    effect = HungerThirstEffect(mock_server_repo)

    assert effect.server_repo == mock_server_repo
    assert effect._counters == {}  # noqa: SLF001
    assert effect._config_cache == {}  # noqa: SLF001


def test_hunger_thirst_effect_get_interval(mock_server_repo: AsyncMock) -> None:
    """Test que verifica que el intervalo es 1 segundo."""
    effect = HungerThirstEffect(mock_server_repo)
    assert effect.get_interval_seconds() == 1.0


def test_hunger_thirst_effect_get_name(mock_server_repo: AsyncMock) -> None:
    """Test que verifica el nombre del efecto."""
    effect = HungerThirstEffect(mock_server_repo)
    assert effect.get_name() == "HungerThirst"


@pytest.mark.asyncio
async def test_hunger_thirst_effect_reduces_water(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
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
async def test_hunger_thirst_effect_reduces_hunger(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica la reducción de hambre."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # Estado inicial: contador de hambre en el límite
    mock_player_repo.get_hunger_thirst.return_value = {
        "max_water": 100,
        "min_water": 80,
        "max_hunger": 100,
        "min_hunger": 90,
        "thirst_flag": 0,
        "hunger_flag": 0,
        "water_counter": 0,
        "hunger_counter": 5,  # INTERVALO_HAMBRE - 1
    }

    mock_server_repo.get_effect_config_int.side_effect = [4, 6, 10, 10]  # intervalos y reducciones
    effect = HungerThirstEffect(mock_server_repo)

    # Aplicar el efecto (debería reducir hambre)
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se guardó con hambre reducida
    call_kwargs = mock_player_repo.set_hunger_thirst.call_args.kwargs
    assert call_kwargs["min_hunger"] == 80  # 90 - 10
    assert call_kwargs["hunger_counter"] == 0  # Se resetea


@pytest.mark.asyncio
async def test_hunger_thirst_flags_activated(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
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


@pytest.mark.asyncio
async def test_hunger_thirst_no_data(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica el manejo cuando no hay datos de hambre/sed."""
    user_id = 1
    mock_message_sender = AsyncMock()

    # No hay datos de hambre/sed
    mock_player_repo.get_hunger_thirst.return_value = None

    effect = HungerThirstEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que NO se guardó nada
    mock_player_repo.set_hunger_thirst.assert_not_called()


def test_hunger_thirst_cleanup_player(mock_server_repo: AsyncMock) -> None:
    """Test que verifica la limpieza de contadores de un jugador."""
    effect = HungerThirstEffect(mock_server_repo)

    # Agregar contadores manualmente
    effect._counters[1] = {"water": 2, "hunger": 3}  # noqa: SLF001
    effect._counters[2] = {"water": 1, "hunger": 1}  # noqa: SLF001

    # Limpiar jugador 1
    effect.cleanup_player(1)

    # Verificar que se eliminó el jugador 1 pero no el 2
    assert 1 not in effect._counters  # noqa: SLF001
    assert 2 in effect._counters  # noqa: SLF001


@pytest.mark.asyncio
async def test_hunger_thirst_custom_config(
    mock_server_repo: AsyncMock,
    mock_player_repo: AsyncMock,
) -> None:
    """Test que verifica que se usan valores personalizados de configuración."""
    user_id = 1
    mock_message_sender = AsyncMock()

    mock_player_repo.get_hunger_thirst.return_value = {
        "max_water": 100,
        "min_water": 100,
        "max_hunger": 100,
        "min_hunger": 100,
        "thirst_flag": 0,
        "hunger_flag": 0,
        "water_counter": 1,  # INTERVALO_SED - 1 (con intervalo 2)
        "hunger_counter": 0,
    }

    # Configuración personalizada: intervalo 2, reducción 20
    mock_server_repo.get_effect_config_int.side_effect = [2, 6, 20, 10]
    effect = HungerThirstEffect(mock_server_repo)

    # Aplicar el efecto
    await effect.apply(user_id, mock_player_repo, mock_message_sender)

    # Verificar que se usó la reducción personalizada (20)
    call_kwargs = mock_player_repo.set_hunger_thirst.call_args.kwargs
    assert call_kwargs["min_water"] == 80  # 100 - 20
