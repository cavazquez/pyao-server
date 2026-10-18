"""Tests básicos para NPCAIEffect."""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.effects.npc_ai_effect import NPCAIEffect


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
        ai_service.process_hostile_npc = AsyncMock(side_effect=[ValueError("causa real"), None])

        await NPCAIEffect(npc_service, ai_service).apply(1, MagicMock(), None)

        assert ai_service.process_hostile_npc.await_count == 2
        failure = next(record for record in caplog.records if record.levelname == "ERROR")
        assert "instance_id=murcielago-1" in failure.getMessage()
        assert failure.exc_info is not None
        assert str(failure.exc_info[1]) == "causa real"
