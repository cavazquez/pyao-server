"""Tests para TaskDice."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.dice_command import DiceCommand
from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.tasks.task_dice import TaskDice


@pytest.mark.asyncio
async def test_task_dice_generates_attributes() -> None:
    """Verifica que TaskDice genera y envía 5 atributos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)
    message_sender.send_dice_roll = AsyncMock()

    # Mock del handler
    dice_handler = MagicMock()
    dice_handler.handle = AsyncMock(
        return_value=CommandResult.ok(
            data={
                "attributes": {
                    "strength": 15,
                    "agility": 12,
                    "intelligence": 10,
                    "charisma": 8,
                    "constitution": 14,
                }
            }
        )
    )

    # Mock del server_repo
    server_repo = MagicMock()
    server_repo.get_dice_min_value = AsyncMock(return_value=6)
    server_repo.get_dice_max_value = AsyncMock(return_value=18)

    data = bytes([1])  # PacketID ThrowDices
    session_data: dict[str, dict[str, int]] = {}

    task = TaskDice(
        data,
        message_sender,
        dice_handler=dice_handler,
        session_data=session_data,
        server_repo=server_repo,
    )

    await task.execute()

    # Verificar que se llamó al handler
    dice_handler.handle.assert_called_once()
    call_args = dice_handler.handle.call_args[0][0]
    assert isinstance(call_args, DiceCommand)
    assert call_args.min_value == 6
    assert call_args.max_value == 18
