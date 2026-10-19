"""Los eventos visuales no cambian el estado ni se envían a clientes legacy."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.network.capabilities import Capability
from src.network.packet_framer import packet_length
from src.services.visual_events import VisualEvents


@pytest.mark.asyncio
async def test_only_negotiated_observers_receive_one_event_per_commit():
    """Un recibo se publica una vez y nunca agrega bytes a una conexión legacy."""
    modern = SimpleNamespace(
        connection=SimpleNamespace(
            capabilities=SimpleNamespace(enabled=Capability.VISUAL_DAMAGE | Capability.PROJECTILES),
            send=AsyncMock(),
        )
    )
    legacy = SimpleNamespace(
        connection=SimpleNamespace(
            capabilities=SimpleNamespace(enabled=Capability.NONE), send=AsyncMock()
        )
    )
    maps = SimpleNamespace(
        get_players_in_map=lambda m: [1, 2] if m == 7 else [],
        get_player_message_sender=lambda u: {1: modern, 2: legacy}[u],
    )
    events = VisualEvents(maps)
    for _ in range(2):
        await events.damage("commit-a", 7, 2, 50, 51, 20, 4)
    modern.connection.send.assert_awaited_once()
    legacy.connection.send.assert_not_awaited()
    frame = modern.connection.send.await_args.args[0]
    assert frame[0] == 246
    assert packet_length(frame, "server") == len(frame)


@pytest.mark.asyncio
async def test_simultaneous_casts_keep_source_and_identity_and_are_bounded():
    """Dos lanzadores conservan sus extremos y una coordenada inválida se rechaza."""
    frames = []
    observer = SimpleNamespace(
        connection=SimpleNamespace(
            capabilities=SimpleNamespace(enabled=Capability.PROJECTILES),
            send=AsyncMock(side_effect=frames.append),
        )
    )
    maps = SimpleNamespace(
        get_players_in_map=lambda _m: [1], get_player_message_sender=lambda _u: observer
    )
    events = VisualEvents(maps)
    await events.projectile("cast-a", 2, 1, 2, 10, 10, 11, 10, 1, 7, 2)
    await events.projectile("cast-b", 2, 2, 1, 11, 10, 10, 10, 1, 7, 2)
    assert len(frames) == 2
    assert frames[0] != frames[1]
    assert all(packet_length(frame, "server") == len(frame) for frame in frames)
    with pytest.raises(ValueError, match="fuera de rango"):
        await events.projectile("invalid", 2, 1, 2, 0, 10, 11, 10, 1, 7, 2)
    assert len(frames) == 2
