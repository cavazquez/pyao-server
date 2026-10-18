"""Targeting optativo fragmentado y concatenado, nunca deducido del read TCP."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.network.capabilities import Capability
from src.network.packet_framer import PacketFramer
from src.tasks.spells.task_cast_spell import TaskCastSpell


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("x", "y", "slot", "version", "authenticated", "mask", "accepted"),
    [
        (55, 50, 1, 1, True, 2, True),
        (0, 50, 1, 1, True, 2, False),
        (101, 50, 1, 1, True, 2, False),
        (50, -1, 1, 1, True, 2, False),
        (50, 50, 0, 1, True, 2, False),
        (50, 50, 36, 1, True, 2, False),
        (50, 50, 1, 2, True, 2, False),
        (50, 50, 1, 1, False, 2, False),
        (50, 50, 1, 1, True, 0, False),
    ],
)
async def test_target_validation(
    x: int, y: int, slot: int, version: int, *, authenticated: bool, mask: int, accepted: bool
) -> None:
    """Sin capacidad, autenticación o coordenadas válidas no se invoca el efecto."""
    sender = AsyncMock()
    sender.connection = MagicMock(is_authenticated=authenticated)
    sender.connection.capabilities.enabled = Capability(mask)
    handler = AsyncMock()
    handler.handle.return_value = CommandResult.ok()
    packet = struct.pack("<BBBhh", 253, version, slot, x, y)
    await TaskCastSpell(packet, sender, handler, {"user_id": 1}).execute()
    assert handler.handle.call_count == int(accepted)
    if accepted:
        command = handler.handle.call_args.args[0]
        assert (command.slot, command.target_x, command.target_y) == (slot, x, y)


def test_fragmentation_and_coalescing() -> None:
    """Legacy seguido de ping nunca roba bytes del paquete siguiente."""
    legacy = bytes([25, 1])
    targeted = struct.pack("<BBBhh", 253, 1, 1, 55, 50)
    expected = [legacy, bytes([119]), targeted, bytes([119])]
    wire = b"".join(expected)
    for split in range(len(wire) + 1):
        framer = PacketFramer()
        actual = []
        for chunk in (wire[:split], wire[split:]):
            framer.feed(chunk)
            while (packet := framer.next_packet()) is not None:
                actual.append(packet)
        assert actual == expected
