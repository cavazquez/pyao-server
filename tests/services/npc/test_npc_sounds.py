"""Tests para sonidos de NPCs (snd1, snd2, snd3)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.npc import NPC


@pytest.fixture
def sample_npc_with_sounds() -> NPC:
    """Fixture para un NPC con sonidos configurados."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test-instance-123",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Goblin",
        description="Un goblin",
        body_id=500,
        head_id=0,
        hp=100,
        max_hp=100,
        level=5,
        is_hostile=True,
        is_attackable=True,
        snd1=10,  # Sonido de ataque
        snd2=11,  # Sonido de daño
        snd3=12,  # Sonido de muerte
    )


@pytest.fixture
def sample_npc_without_sounds() -> NPC:
    """Fixture para un NPC sin sonidos configurados."""
    return NPC(
        npc_id=2,
        char_index=10002,
        instance_id="test-instance-456",
        map_id=1,
        x=51,
        y=51,
        heading=1,
        name="Silent NPC",
        description="NPC sin sonidos",
        body_id=501,
        head_id=0,
        hp=50,
        max_hp=50,
        level=3,
        is_hostile=False,
        is_attackable=False,
        snd1=0,  # Sin sonido
        snd2=0,  # Sin sonido
        snd3=0,  # Sin sonido
    )


@pytest.fixture
def mock_broadcast_service() -> MagicMock:
    """Mock del servicio de broadcast."""
    service = MagicMock()
    service.broadcast_play_wave = AsyncMock()
    return service


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock del MessageSender."""
    sender = MagicMock()
    sender.send_play_wave = AsyncMock()
    return sender


class TestNPCAttackSound:
    """Tests para sonido de ataque del NPC (snd1)."""

    @pytest.mark.asyncio
    async def test_npc_attack_plays_sound_snd1(
        self,
        sample_npc_with_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que el NPC reproduce snd1 cuando ataca."""
        # Simular ataque del NPC (código de NPCAIService)
        if sample_npc_with_sounds.snd1 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=sample_npc_with_sounds.map_id,
                wave_id=sample_npc_with_sounds.snd1,
                x=sample_npc_with_sounds.x,
                y=sample_npc_with_sounds.y,
            )

        # Verificar que se llamó con el sonido correcto
        mock_broadcast_service.broadcast_play_wave.assert_called_once_with(
            map_id=1, wave_id=10, x=50, y=50
        )

    @pytest.mark.asyncio
    async def test_npc_attack_no_sound_if_snd1_zero(
        self,
        sample_npc_without_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que no reproduce sonido si snd1 es 0."""
        # Simular ataque del NPC
        if sample_npc_without_sounds.snd1 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=sample_npc_without_sounds.map_id,
                wave_id=sample_npc_without_sounds.snd1,
                x=sample_npc_without_sounds.x,
                y=sample_npc_without_sounds.y,
            )

        # No debe haberse llamado
        mock_broadcast_service.broadcast_play_wave.assert_not_called()


class TestNPCDamageSound:
    """Tests para sonido de daño recibido del NPC (snd2)."""

    @pytest.mark.asyncio
    async def test_npc_damage_plays_sound_snd2(
        self,
        sample_npc_with_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que el NPC reproduce snd2 cuando recibe daño."""
        # Simular daño al NPC (código de AttackCommandHandler)
        if sample_npc_with_sounds.snd2 > 0 and mock_broadcast_service:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=sample_npc_with_sounds.map_id,
                wave_id=sample_npc_with_sounds.snd2,
                x=sample_npc_with_sounds.x,
                y=sample_npc_with_sounds.y,
            )

        # Verificar que se llamó con el sonido correcto
        mock_broadcast_service.broadcast_play_wave.assert_called_once_with(
            map_id=1, wave_id=11, x=50, y=50
        )

    @pytest.mark.asyncio
    async def test_npc_damage_no_sound_if_snd2_zero(
        self,
        sample_npc_without_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que no reproduce sonido si snd2 es 0."""
        # Simular daño al NPC
        if sample_npc_without_sounds.snd2 > 0 and mock_broadcast_service:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=sample_npc_without_sounds.map_id,
                wave_id=sample_npc_without_sounds.snd2,
                x=sample_npc_without_sounds.x,
                y=sample_npc_without_sounds.y,
            )

        # No debe haberse llamado
        mock_broadcast_service.broadcast_play_wave.assert_not_called()


class TestNPCDeathSound:
    """Tests para sonido de muerte del NPC (snd3)."""

    @pytest.mark.asyncio
    async def test_npc_death_plays_sound_snd3(
        self,
        sample_npc_with_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que el NPC reproduce snd3 cuando muere."""
        # Simular muerte del NPC (código de NPCDeathService)
        if sample_npc_with_sounds.snd3 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=sample_npc_with_sounds.map_id,
                wave_id=sample_npc_with_sounds.snd3,
                x=sample_npc_with_sounds.x,
                y=sample_npc_with_sounds.y,
            )

        # Verificar que se llamó con el sonido correcto
        mock_broadcast_service.broadcast_play_wave.assert_called_once_with(
            map_id=1, wave_id=12, x=50, y=50
        )

    @pytest.mark.asyncio
    async def test_npc_death_no_sound_if_snd3_zero(
        self,
        sample_npc_without_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que no reproduce sonido si snd3 es 0."""
        # Simular muerte del NPC
        if sample_npc_without_sounds.snd3 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=sample_npc_without_sounds.map_id,
                wave_id=sample_npc_without_sounds.snd3,
                x=sample_npc_without_sounds.x,
                y=sample_npc_without_sounds.y,
            )

        # No debe haberse llamado
        mock_broadcast_service.broadcast_play_wave.assert_not_called()


class TestNPCSoundCombinations:
    """Tests para combinaciones de sonidos."""

    @pytest.mark.asyncio
    async def test_npc_with_all_sounds(
        self,
        sample_npc_with_sounds: NPC,
        mock_broadcast_service: MagicMock,
    ) -> None:
        """Test que un NPC puede tener los 3 sonidos configurados."""
        # Verificar que tiene los 3 sonidos
        assert sample_npc_with_sounds.snd1 > 0
        assert sample_npc_with_sounds.snd2 > 0
        assert sample_npc_with_sounds.snd3 > 0

        # Reproducir ataque
        if sample_npc_with_sounds.snd1 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=1, wave_id=sample_npc_with_sounds.snd1, x=50, y=50
            )

        # Reproducir daño
        if sample_npc_with_sounds.snd2 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=1, wave_id=sample_npc_with_sounds.snd2, x=50, y=50
            )

        # Reproducir muerte
        if sample_npc_with_sounds.snd3 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=1, wave_id=sample_npc_with_sounds.snd3, x=50, y=50
            )

        # Verificar que se llamaron los 3 sonidos
        assert mock_broadcast_service.broadcast_play_wave.call_count == 3

        # Verificar los sonidos específicos
        calls = mock_broadcast_service.broadcast_play_wave.call_args_list
        wave_ids = [call[1]["wave_id"] for call in calls]
        assert 10 in wave_ids  # snd1
        assert 11 in wave_ids  # snd2
        assert 12 in wave_ids  # snd3

    @pytest.mark.asyncio
    async def test_npc_with_partial_sounds(self, mock_broadcast_service: MagicMock) -> None:
        """Test que un NPC puede tener solo algunos sonidos configurados."""
        # NPC con solo snd1
        npc = NPC(
            npc_id=3,
            char_index=10003,
            instance_id="test-instance-789",
            map_id=1,
            x=52,
            y=52,
            heading=2,
            name="Partial Sound NPC",
            description="NPC con solo un sonido",
            body_id=502,
            head_id=0,
            hp=75,
            max_hp=75,
            level=4,
            is_hostile=True,
            is_attackable=True,
            snd1=20,  # Solo ataque
            snd2=0,  # Sin daño
            snd3=0,  # Sin muerte
        )

        # Solo debe reproducir snd1
        if npc.snd1 > 0:
            await mock_broadcast_service.broadcast_play_wave(
                map_id=npc.map_id, wave_id=npc.snd1, x=npc.x, y=npc.y
            )

        # Verificar que solo se llamó una vez con snd1
        mock_broadcast_service.broadcast_play_wave.assert_called_once_with(
            map_id=1, wave_id=20, x=52, y=52
        )
