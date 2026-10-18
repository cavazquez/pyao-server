"""Contrato legacy exacto: ID 25 y slot, sin padding ni heurísticas TCP."""

from unittest.mock import AsyncMock

import pytest

from src.commands.base import CommandResult
from src.tasks.spells.task_cast_spell import TaskCastSpell


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "session", "accepted"),
    [
        (b"\x19\x01", {"user_id": 1}, True),
        (b"\x19\x01", {}, False),
        (b"\x19", {"user_id": 1}, False),
        (b"\x19\x00", {"user_id": 1}, False),
        (b"\x19\x01\x00", {"user_id": 1}, False),
    ],
)
async def test_legacy_exact(data: bytes, session: dict[str, int], *, accepted: bool) -> None:
    """La tarea acepta únicamente la trama completa definida por el contrato."""
    handler = AsyncMock()
    handler.handle.return_value = CommandResult.ok()
    task = TaskCastSpell(data, AsyncMock(), handler, session)
    await task.execute()
    assert handler.handle.call_count == int(accepted)
    if accepted:
        command = handler.handle.call_args.args[0]
        assert command.slot == 1
        assert command.target_x is None
        assert command.target_y is None
