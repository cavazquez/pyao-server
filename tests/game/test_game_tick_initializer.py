"""Tests para GameTickInitializer."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.core.game_tick_initializer import GameTickInitializer
from src.game.game_tick import GameTick


@pytest.mark.asyncio
async def test_game_tick_initializer_creates_game_tick() -> None:
    """Verifica que GameTickInitializer crea un GameTick."""
    player_repo = Mock()
    server_repo = Mock()
    server_repo.get_effect_config_bool = AsyncMock(return_value=True)
    map_manager = Mock()
    npc_service = Mock()
    npc_ai_service = Mock()

    stamina_service = Mock()

    initializer = GameTickInitializer(
        player_repo, server_repo, map_manager, npc_service, npc_ai_service, stamina_service
    )

    game_tick = await initializer.initialize()

    assert isinstance(game_tick, GameTick)
    assert game_tick.player_repo is player_repo
    assert game_tick.map_manager is map_manager


@pytest.mark.asyncio
async def test_game_tick_initializer_adds_effects() -> None:
    """Verifica que GameTickInitializer agrega efectos al GameTick."""
    player_repo = Mock()
    server_repo = Mock()
    server_repo.get_effect_config_bool = AsyncMock(return_value=True)
    map_manager = Mock()
    npc_service = Mock()
    npc_ai_service = Mock()

    stamina_service = Mock()

    initializer = GameTickInitializer(
        player_repo, server_repo, map_manager, npc_service, npc_ai_service, stamina_service
    )

    game_tick = await initializer.initialize()

    # Verificar que se agregaron efectos
    assert len(game_tick.effects) > 0


@pytest.mark.asyncio
async def test_game_tick_initializer_respects_config() -> None:
    """Verifica que GameTickInitializer respeta la configuración de efectos."""
    player_repo = Mock()
    server_repo = Mock()
    # Deshabilitar efectos opcionales
    server_repo.get_effect_config_bool = AsyncMock(return_value=False)
    map_manager = Mock()
    npc_service = Mock()
    npc_ai_service = Mock()

    stamina_service = Mock()

    initializer = GameTickInitializer(
        player_repo, server_repo, map_manager, npc_service, npc_ai_service, stamina_service
    )

    game_tick = await initializer.initialize()

    # Debería tener al menos el efecto de meditación (siempre habilitado)
    # y los efectos de NPC (movimiento e IA)
    assert len(game_tick.effects) >= 3
