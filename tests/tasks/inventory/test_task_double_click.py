"""Regresiones del contrato de doble clic de mapa, independiente de inventario."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.left_click_command import LeftClickCommand
from src.tasks.inventory.task_double_click import TaskDoubleClick


@pytest.mark.asyncio
@pytest.mark.parametrize(("x", "y"), [(1, 1), (25, 30), (50, 51), (100, 100)])
async def test_double_click_uses_map_coordinates_not_inventory_slot(x: int, y: int) -> None:
    """Incluso x=25/30 se delega como mapa y no usa un item."""
    handler = MagicMock(handle=AsyncMock(return_value=CommandResult.ok()))
    repository = MagicMock(get_position=AsyncMock(return_value={"map": 7, "x": 50, "y": 50}))
    sender = MagicMock(send_console_msg=AsyncMock())
    task = TaskDoubleClick(
        bytes([27, x, y]),
        sender,
        left_click_handler=handler,
        player_repo=repository,
        session_data={"user_id": 10},
    )
    await task.execute()
    handler.handle.assert_awaited_once()
    command = handler.handle.call_args.args[0]
    assert isinstance(command, LeftClickCommand)
    assert (command.user_id, command.map_id, command.x, command.y) == (10, 7, x, y)
    repository.use_item.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("data", "session"),
    [
        (b"\x1b", {"user_id": 1}),
        (b"\x1b\x05", {"user_id": 1}),
        (b"\x1b\x00\x32", {"user_id": 1}),
        (b"\x1b\x32\x65", {"user_id": 1}),
        (b"\x1b\x32\x32\x06\x01", {"user_id": 1}),
        (b"\x1b\x32\x32", {}),
    ],
)
async def test_invalid_or_unauthenticated_double_click_does_not_mutate(data, session) -> None:
    """Truncado, coordenadas inválidas y formato con bytes sobrantes no se ejecutan."""
    handler = MagicMock(handle=AsyncMock())
    repository = MagicMock(get_position=AsyncMock())
    sender = MagicMock(send_console_msg=AsyncMock())
    await TaskDoubleClick(
        data,
        sender,
        left_click_handler=handler,
        player_repo=repository,
        session_data=session,
    ).execute()
    handler.handle.assert_not_called()
    repository.get_position.assert_not_called()
