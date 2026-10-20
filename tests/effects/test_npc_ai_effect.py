"""Tests básicos para NPCAIEffect."""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effects.npc_ai_effect import NPCAIEffect
from src.game.game_tick import GameTick


class TestNPCAIEffect:
    """Tests básicos para NPCAIEffect."""

    def test_init_default(self) -> None:
        """Test de inicialización con valores por defecto."""
        npc_service = MagicMock()
        npc_ai_service = MagicMock()

        effect = NPCAIEffect(npc_service, npc_ai_service)

        assert effect.npc_service == npc_service
        assert effect.npc_ai_service == npc_ai_service
        assert math.isclose(effect.interval_seconds, 2.0)

    def test_init_custom_interval(self) -> None:
        """Test de inicialización con intervalo personalizado."""
        npc_service = MagicMock()
        npc_ai_service = MagicMock()

        effect = NPCAIEffect(npc_service, npc_ai_service, interval_seconds=2.0)

        assert math.isclose(effect.interval_seconds, 2.0)

    def test_get_interval_seconds(self) -> None:
        """Test de obtención del intervalo."""
        npc_service = MagicMock()
        npc_ai_service = MagicMock()

        effect = NPCAIEffect(npc_service, npc_ai_service, interval_seconds=1.5)

        assert math.isclose(effect.get_interval_seconds(), 1.5)

    def test_get_name(self) -> None:
        """Test de obtención del nombre del efecto."""
        npc_service = MagicMock()
        npc_ai_service = MagicMock()

        effect = NPCAIEffect(npc_service, npc_ai_service)

        assert effect.get_name() == "NPCAI"

    @pytest.mark.asyncio
    async def test_failure_records_npc_and_traceback_without_stopping_others(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Un fallo aislado conserva su causa y no impide procesar el otro NPC."""
        failed = MagicMock(instance_id="murcielago-1", map_id=1, x=50, y=51, is_hostile=True, hp=15)
        failed.name = "Murciélago"
        healthy = MagicMock(is_hostile=True, hp=15, map_id=1)
        npc_service = MagicMock()
        npc_service.map_manager.get_all_npcs.return_value = [failed, healthy]
        npc_service.map_manager.get_maps_with_players.return_value = [1]
        ai_service = MagicMock()
        ai_service.player_repo.get_positions = AsyncMock(return_value={})
        ai_service.process_hostile_npc = AsyncMock(side_effect=[ValueError("causa real"), None])

        await NPCAIEffect(npc_service, ai_service).apply(1, MagicMock(), None)

        assert ai_service.process_hostile_npc.await_count == 2
        failure = next(record for record in caplog.records if record.levelname == "ERROR")
        assert "instance_id=murcielago-1" in failure.getMessage()
        assert failure.exc_info is not None
        assert str(failure.exc_info[1]) == "causa real"


@pytest.mark.asyncio
async def test_ai_reads_each_map_once_per_tick_and_drops_snapshot() -> None:
    """Muchos NPCs comparten los candidatos de su mapa, sin reutilizarlos al siguiente tick."""
    service, ai = MagicMock(), MagicMock()
    npcs = [MagicMock(is_hostile=True, hp=10, map_id=mid) for mid in (1, 1, 1, 2, 2)]
    service.map_manager.get_all_npcs.return_value = npcs
    service.map_manager.get_maps_with_players.return_value = [1, 2]
    service.map_manager.get_players_in_map.side_effect = lambda mid: [mid * 10]
    first = {10: {"map": 1, "x": 50, "y": 50}}
    second = {20: {"map": 2, "x": 50, "y": 50}}
    ai.player_repo.get_positions = AsyncMock(side_effect=[first, second, {}, {}])
    ai.process_hostile_npc = AsyncMock()
    effect = NPCAIEffect(service, ai)
    await effect.apply(1, MagicMock(), None)
    calls = ai.process_hostile_npc.await_args_list
    assert all(call.kwargs["candidate_positions"] is first for call in calls[:3])
    assert all(call.kwargs["candidate_positions"] is second for call in calls[3:])
    ai.player_repo.get_positions.assert_any_await([10], alive_only=True)
    ai.player_repo.get_positions.assert_any_await([20], alive_only=True)
    assert ai.player_repo.get_positions.await_count == 2
    ai.process_hostile_npc.reset_mock()
    await effect.apply(1, MagicMock(), None)
    assert ai.player_repo.get_positions.await_count == 4
    assert all(
        call.kwargs["candidate_positions"] == {} for call in ai.process_hostile_npc.await_args_list
    )


@pytest.mark.asyncio
async def test_game_tick_schedules_ai_once_for_all_connected_players() -> None:
    """El costo de IA global no se multiplica por la cantidad de usuarios conectados."""
    effect = NPCAIEffect(MagicMock(), MagicMock())
    manager = MagicMock()
    manager.get_all_connected_user_ids.return_value = [1, 2, 3]
    per_player = MagicMock(runs_once_per_tick=False)
    per_player.apply = AsyncMock()
    per_player.get_name.return_value = "per-player"
    tick = GameTick(MagicMock(), manager, effects=[effect, per_player], tick_interval=0)

    async def stop_after_first(*_args: object) -> None:
        tick._running = False

    effect.apply = AsyncMock(side_effect=stop_after_first)
    tick._running = True
    await tick._tick_loop()
    assert effect.apply.await_count == 1
    assert per_player.apply.await_count == 3


@pytest.mark.asyncio
async def test_bad_candidate_map_does_not_skip_other_maps(caplog: pytest.LogCaptureFixture) -> None:
    """Un snapshot inválido falla cerrado para ese mapa y conserva la IA de los demás."""
    service, ai = MagicMock(), MagicMock()
    bad = MagicMock(is_hostile=True, hp=10, map_id=1)
    good = MagicMock(is_hostile=True, hp=10, map_id=2)
    service.map_manager.get_all_npcs.return_value = [bad, good]
    service.map_manager.get_maps_with_players.return_value = [1, 2]
    ai.player_repo.get_positions = AsyncMock(side_effect=[ValueError("invalid HP"), {}])
    ai.process_hostile_npc = AsyncMock()
    await NPCAIEffect(service, ai).apply(1, MagicMock(), None)
    ai.process_hostile_npc.assert_awaited_once_with(good, candidate_positions={})
    assert "candidatos de IA del mapa 1" in caplog.text
