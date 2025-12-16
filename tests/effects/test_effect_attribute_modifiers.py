"""Tests para AttributeModifiersEffect."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effects.effect_attribute_modifiers import AttributeModifiersEffect
from src.models.player_stats import PlayerAttributes


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_strength_modifier = AsyncMock(return_value=(0.0, 0))
    repo.get_agility_modifier = AsyncMock(return_value=(0.0, 0))
    repo.set_strength_modifier = AsyncMock()
    repo.set_agility_modifier = AsyncMock()

    repo.get_player_attributes = AsyncMock(
        return_value=PlayerAttributes(
            strength=15, agility=14, intelligence=10, charisma=10, constitution=10
        )
    )
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_update_strength_and_dexterity = AsyncMock()
    return sender


@pytest.mark.asyncio
async def test_apply_no_modifiers_expired(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando no hay modificadores expirados."""
    effect = AttributeModifiersEffect(interval_seconds=10.0)

    await effect.apply(1, mock_player_repo, mock_message_sender)

    mock_player_repo.get_strength_modifier.assert_called_once_with(1)
    mock_player_repo.get_agility_modifier.assert_called_once_with(1)
    mock_message_sender.send_update_strength_and_dexterity.assert_not_called()


@pytest.mark.asyncio
async def test_apply_strength_modifier_expired(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el modificador de fuerza expira."""
    # Modificador expirado (timestamp pasado)
    expired_time = time.time() - 100
    mock_player_repo.get_strength_modifier = AsyncMock(return_value=(expired_time, 5))
    mock_player_repo.get_agility_modifier = AsyncMock(return_value=(0.0, 0))

    effect = AttributeModifiersEffect(interval_seconds=10.0)

    await effect.apply(1, mock_player_repo, mock_message_sender)

    mock_player_repo.set_strength_modifier.assert_called_once_with(1, 0.0, 0)
    mock_player_repo.set_agility_modifier.assert_not_called()
    mock_message_sender.send_update_strength_and_dexterity.assert_called_once()


@pytest.mark.asyncio
async def test_apply_agility_modifier_expired(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando el modificador de agilidad expira."""
    expired_time = time.time() - 100
    mock_player_repo.get_strength_modifier = AsyncMock(return_value=(0.0, 0))
    mock_player_repo.get_agility_modifier = AsyncMock(return_value=(expired_time, 3))

    effect = AttributeModifiersEffect(interval_seconds=10.0)

    await effect.apply(1, mock_player_repo, mock_message_sender)

    mock_player_repo.set_agility_modifier.assert_called_once_with(1, 0.0, 0)
    mock_player_repo.set_strength_modifier.assert_not_called()
    mock_message_sender.send_update_strength_and_dexterity.assert_called_once()


@pytest.mark.asyncio
async def test_apply_both_modifiers_expired(
    mock_player_repo: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Test cuando ambos modificadores expiran."""
    expired_time = time.time() - 100
    mock_player_repo.get_strength_modifier = AsyncMock(return_value=(expired_time, 5))
    mock_player_repo.get_agility_modifier = AsyncMock(return_value=(expired_time, 3))

    effect = AttributeModifiersEffect(interval_seconds=10.0)

    await effect.apply(1, mock_player_repo, mock_message_sender)

    mock_player_repo.set_strength_modifier.assert_called_once()
    mock_player_repo.set_agility_modifier.assert_called_once()
    mock_message_sender.send_update_strength_and_dexterity.assert_called_once()


@pytest.mark.asyncio
async def test_apply_no_message_sender(
    mock_player_repo: MagicMock,
) -> None:
    """Test cuando no hay message_sender."""
    expired_time = time.time() - 100
    mock_player_repo.get_strength_modifier = AsyncMock(return_value=(expired_time, 5))
    mock_player_repo.get_agility_modifier = AsyncMock(return_value=(0.0, 0))

    effect = AttributeModifiersEffect(interval_seconds=10.0)

    await effect.apply(1, mock_player_repo, None)

    mock_player_repo.set_strength_modifier.assert_called_once()
    # No debe fallar aunque no haya message_sender


@pytest.mark.asyncio
async def test_get_interval_seconds() -> None:
    """Test obtener intervalo de segundos."""
    effect = AttributeModifiersEffect(interval_seconds=15.0)
    assert effect.get_interval_seconds() == 15.0


@pytest.mark.asyncio
async def test_get_name() -> None:
    """Test obtener nombre del efecto."""
    effect = AttributeModifiersEffect()
    assert effect.get_name() == "AttributeModifiers"
