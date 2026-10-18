"""Tests para PoisonEffect."""

import math
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effects.effect_poison import POISON_DAMAGE_PER_TICK, PoisonEffect
from src.models.player_stats import PlayerStats


@pytest.fixture
def mock_player_repo(monkeypatch) -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_poisoned_until = AsyncMock(return_value=0.0)
    repo.update_poisoned_until = AsyncMock()
    repo.clear_poisoned_until_if = AsyncMock()
    repo.is_alive = AsyncMock(return_value=True)
    repo.get_player_stats = AsyncMock(return_value=PlayerStats(min_hp=100, max_hp=100))
    repo.update_hp = AsyncMock()

    async def damage_commit(_redis, _user_id, amount, _identity, **_kwargs: object):
        stats = await repo.get_player_stats(1)
        hp = max(0, stats.min_hp - amount)
        return {"new_hp": hp, "life_id": 0, "player_died": hp <= 0}

    repo.damage_commit = AsyncMock(side_effect=damage_commit)
    monkeypatch.setattr("src.effects.effect_poison.apply_player_damage", repo.damage_commit)
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_update_user_stats = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_apply_not_poisoned(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el jugador no está envenenado."""
    effect = PoisonEffect()

    await effect.apply(1, mock_player_repo, mock_message_sender)

    mock_player_repo.get_poisoned_until.assert_called_once_with(1)
    mock_player_repo.update_hp.assert_not_called()


@pytest.mark.asyncio
async def test_apply_poison_expired(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el veneno ha expirado."""
    expired_time = time.time() - 100
    mock_player_repo.get_poisoned_until = AsyncMock(return_value=expired_time)

    effect = PoisonEffect()

    await effect.apply(1, mock_player_repo, mock_message_sender)

    mock_player_repo.clear_poisoned_until_if.assert_awaited_once_with(1, expired_time)
    mock_player_repo.update_hp.assert_not_called()


@pytest.mark.asyncio
async def test_apply_poison_damage(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test aplicar daño de veneno."""
    future_time = time.time() + 30
    mock_player_repo.get_poisoned_until = AsyncMock(return_value=future_time)
    mock_player_repo.get_player_stats = AsyncMock(return_value=PlayerStats(min_hp=100, max_hp=100))

    effect = PoisonEffect()

    await effect.apply(1, mock_player_repo, mock_message_sender)

    # Verificar que se actualizó el HP con el daño
    mock_player_repo.damage_commit.assert_awaited_once()
    assert (
        mock_message_sender.send_update_user_stats.call_args.kwargs["min_hp"]
        == 100 - POISON_DAMAGE_PER_TICK
    )
    mock_message_sender.send_update_user_stats.assert_called_once()


@pytest.mark.asyncio
async def test_apply_poison_kills_player(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el veneno mata al jugador."""
    future_time = time.time() + 30
    mock_player_repo.get_poisoned_until = AsyncMock(return_value=future_time)
    mock_player_repo.get_player_stats = AsyncMock(return_value=PlayerStats(min_hp=3, max_hp=100))

    effect = PoisonEffect()

    await effect.apply(1, mock_player_repo, mock_message_sender)

    # Verificar que el HP llegó a 0 (3 - 5 = -2, pero max(0, -2) = 0)
    mock_player_repo.damage_commit.assert_awaited_once()
    assert mock_message_sender.send_update_user_stats.call_args.kwargs["min_hp"] == 0
    # La limpieza pertenece al commit letal, evitando mutar una vida posterior.
    mock_player_repo.update_poisoned_until.assert_not_called()


@pytest.mark.asyncio
async def test_apply_player_dead(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el jugador ya está muerto."""
    future_time = time.time() + 30
    mock_player_repo.get_poisoned_until = AsyncMock(return_value=future_time)
    mock_player_repo.is_alive = AsyncMock(return_value=False)

    effect = PoisonEffect()

    await effect.apply(1, mock_player_repo, mock_message_sender)

    # La limpieza pertenece al commit letal, evitando mutar una vida posterior.
    mock_player_repo.update_poisoned_until.assert_not_called()
    mock_player_repo.update_hp.assert_not_called()


@pytest.mark.asyncio
async def test_get_interval_seconds() -> None:
    """Test obtener intervalo de segundos."""
    effect = PoisonEffect(interval_seconds=2.0)
    assert math.isclose(effect.get_interval_seconds(), 2.0)


@pytest.mark.asyncio
async def test_get_name() -> None:
    """Test obtener nombre del efecto."""
    effect = PoisonEffect()
    assert effect.get_name() == "Poison"
