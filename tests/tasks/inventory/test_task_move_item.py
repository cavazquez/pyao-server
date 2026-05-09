"""Tests para TaskMoveItem y MoveItemCommandHandler."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.move_item_command import MoveItemCommand
from src.command_handlers.move_item_handler import MoveItemCommandHandler
from src.network.packet_id import ClientPacketID
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.validation_result import ValidationResult
from src.repositories.inventory_repository import SwapSlotsResult
from src.tasks.inventory.task_move_item import TaskMoveItem


def create_mock_move_item_handler(
    inventory_repo: MagicMock | None = None,
    item_catalog: MagicMock | None = None,
    message_sender: MagicMock | None = None,
) -> MagicMock:
    """Crea un mock de MoveItemCommandHandler con las dependencias especificadas."""
    handler = MagicMock()
    handler.inventory_repo = inventory_repo or MagicMock()
    handler.item_catalog = item_catalog or MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


@pytest.mark.asyncio
class TestTaskMoveItem:
    """Tests para el task MOVE_ITEM."""

    async def test_move_item_success(self) -> None:
        """Intercambia slots correctamente."""
        message_sender = MagicMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        move_item_handler = create_mock_move_item_handler(message_sender=message_sender)
        move_item_handler.handle.return_value = CommandResult.ok(
            data={"old_slot": 1, "new_slot": 5}
        )

        # Packet: MOVE_ITEM + old_slot=1 + new_slot=5
        task = TaskMoveItem(
            data=bytes([ClientPacketID.MOVE_ITEM, 1, 5]),
            message_sender=message_sender,
            move_item_handler=move_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        move_item_handler.handle.assert_called_once()
        call_args = move_item_handler.handle.call_args[0][0]
        assert isinstance(call_args, MoveItemCommand)
        assert call_args.user_id == 1
        assert call_args.old_slot == 1
        assert call_args.new_slot == 5

    async def test_move_item_without_session(self) -> None:
        """Ignora la petición si no hay sesión activa."""
        message_sender = MagicMock()
        move_item_handler = create_mock_move_item_handler()

        task = TaskMoveItem(
            data=bytes([ClientPacketID.MOVE_ITEM, 1, 5]),
            message_sender=message_sender,
            move_item_handler=move_item_handler,
            session_data={},
        )

        await task.execute()

        move_item_handler.handle.assert_not_called()

    async def test_move_item_invalid_packet_too_short(self) -> None:
        """Ignora la petición si el packet es demasiado corto."""
        message_sender = MagicMock()
        move_item_handler = create_mock_move_item_handler()

        task = TaskMoveItem(
            data=bytes([ClientPacketID.MOVE_ITEM]),
            message_sender=message_sender,
            move_item_handler=move_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        move_item_handler.handle.assert_not_called()

    async def test_move_item_handler_error(self) -> None:
        """Maneja error del handler correctamente."""
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        move_item_handler = create_mock_move_item_handler(message_sender=message_sender)
        move_item_handler.handle.return_value = CommandResult.error("Slot fuera de rango")

        task = TaskMoveItem(
            data=bytes([ClientPacketID.MOVE_ITEM, 1, 50]),
            message_sender=message_sender,
            move_item_handler=move_item_handler,
            session_data={"user_id": 1},
        )

        await task.execute()

        move_item_handler.handle.assert_called_once()

    async def test_move_item_parse_payload(self) -> None:
        """Verifica que _parse_payload extrae slots correctamente."""
        old_slot, new_slot = TaskMoveItem._parse_payload(bytes([129, 3, 7]))
        assert old_slot == 3
        assert new_slot == 7

    async def test_move_item_parse_payload_too_short(self) -> None:
        """Verifica que _parse_payload devuelve None para packets cortos."""
        result = TaskMoveItem._parse_payload(bytes([129]))
        assert result == (None, None)

    async def test_move_item_same_slot(self) -> None:
        """El validador rechaza si old_slot == new_slot."""
        data = bytes([ClientPacketID.MOVE_ITEM, 5, 5])
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_move_item_packet()
        assert not result.success


class TestMoveItemPacketValidator:
    """Tests para el validador de MOVE_ITEM."""

    def test_valid_move_item(self) -> None:
        """Valida un packet MOVE_ITEM válido."""
        data = bytes([ClientPacketID.MOVE_ITEM, 1, 5])
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_move_item_packet()
        assert result.success
        assert result.data is not None
        assert result.data["old_slot"] == 1
        assert result.data["new_slot"] == 5

    def test_move_item_same_slot_rejected(self) -> None:
        """Rechaza si old_slot == new_slot."""
        data = bytes([ClientPacketID.MOVE_ITEM, 3, 3])
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_move_item_packet()
        assert not result.success

    def test_move_item_out_of_range(self) -> None:
        """Rechaza slots fuera de rango."""
        data = bytes([ClientPacketID.MOVE_ITEM, 0, 5])
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_move_item_packet()
        assert not result.success

    def test_move_item_second_slot_out_of_range(self) -> None:
        """Rechaza si el segundo slot está fuera de rango."""
        data = bytes([ClientPacketID.MOVE_ITEM, 1, 50])
        reader = PacketReader(data)
        validator = PacketValidator(reader)
        result = validator.validate_move_item_packet()
        assert not result.success


@pytest.mark.asyncio
class TestMoveItemCommandHandler:
    """Tests para MoveItemCommandHandler."""

    async def test_swap_slots_success(self) -> None:
        """Intercambia dos slots correctamente."""
        inventory_repo = MagicMock()
        inventory_repo.swap_slots = AsyncMock(
            return_value=SwapSlotsResult(
                success=True,
                old_slot=1,
                new_slot=5,
                old_slot_data=(100, 3),
                new_slot_data=(200, 1),
            )
        )

        item_catalog = MagicMock()
        item_catalog.get_item_name.side_effect = lambda i: f"Item {i}"
        item_catalog.get_grh_index.side_effect = lambda i: i * 10
        item_catalog.get_item_data.side_effect = lambda i: {"obj_type": 1} if i else None

        message_sender = MagicMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        handler = MoveItemCommandHandler(
            inventory_repo=inventory_repo,
            item_catalog=item_catalog,
            message_sender=message_sender,
        )

        command = MoveItemCommand(user_id=1, old_slot=1, new_slot=5)
        result = await handler.handle(command)

        assert result.success
        inventory_repo.swap_slots.assert_called_once_with(1, 1, 5)
        assert message_sender.send_change_inventory_slot.call_count == 2

    async def test_swap_slots_out_of_bounds(self) -> None:
        """Maneja error cuando los slots están fuera de rango."""
        inventory_repo = MagicMock()
        inventory_repo.swap_slots = AsyncMock(
            return_value=SwapSlotsResult(
                success=False,
                old_slot=1,
                new_slot=50,
                old_slot_data=None,
                new_slot_data=None,
                reason="Slot fuera de rango: new_slot=50",
            )
        )

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        handler = MoveItemCommandHandler(
            inventory_repo=inventory_repo,
            item_catalog=MagicMock(),
            message_sender=message_sender,
        )

        command = MoveItemCommand(user_id=1, old_slot=1, new_slot=50)
        result = await handler.handle(command)

        assert not result.success
        message_sender.send_console_msg.assert_called_once()

    async def test_swap_slots_redis_unavailable(self) -> None:
        """Maneja error cuando Redis no está disponible."""
        inventory_repo = MagicMock()
        inventory_repo.swap_slots = AsyncMock(return_value=None)

        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        handler = MoveItemCommandHandler(
            inventory_repo=inventory_repo,
            item_catalog=MagicMock(),
            message_sender=message_sender,
        )

        command = MoveItemCommand(user_id=1, old_slot=1, new_slot=5)
        result = await handler.handle(command)

        assert not result.success
        assert result.error_message

    async def test_swap_slots_empty_to_empty(self) -> None:
        """Intercambia slots donde ambos están vacíos."""
        inventory_repo = MagicMock()
        inventory_repo.swap_slots = AsyncMock(
            return_value=SwapSlotsResult(
                success=True,
                old_slot=1,
                new_slot=5,
                old_slot_data=None,
                new_slot_data=None,
            )
        )

        message_sender = MagicMock()
        message_sender.send_change_inventory_slot = AsyncMock()
        message_sender.send_console_msg = AsyncMock()

        item_catalog = MagicMock()

        handler = MoveItemCommandHandler(
            inventory_repo=inventory_repo,
            item_catalog=item_catalog,
            message_sender=message_sender,
        )

        command = MoveItemCommand(user_id=1, old_slot=1, new_slot=5)
        result = await handler.handle(command)

        assert result.success
        # Should send empty slots
        assert message_sender.send_change_inventory_slot.call_count == 2