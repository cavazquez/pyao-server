"""Tests básicos para NPCAIEffect."""

import math
from unittest.mock import MagicMock

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
