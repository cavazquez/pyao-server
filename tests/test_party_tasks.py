"""Tests for Party Task Handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.party_accept_command import PartyAcceptCommand
from src.commands.party_create_command import PartyCreateCommand
from src.commands.party_join_command import PartyJoinCommand
from src.commands.party_kick_command import PartyKickCommand
from src.commands.party_leave_command import PartyLeaveCommand
from src.commands.party_message_command import PartyMessageCommand
from src.commands.party_set_leader_command import PartySetLeaderCommand
from src.tasks.task_party_accept_member import TaskPartyAcceptMember
from src.tasks.task_party_create import TaskPartyCreate
from src.tasks.task_party_join import TaskPartyJoin
from src.tasks.task_party_kick import TaskPartyKick
from src.tasks.task_party_leave import TaskPartyLeave
from src.tasks.task_party_message import TaskPartyMessage
from src.tasks.task_party_set_leader import TaskPartySetLeader


@pytest.fixture
def mock_message_sender():
    """Create a mock message sender."""
    return AsyncMock()


@pytest.fixture
def mock_connection():
    """Create a mock connection."""
    return MagicMock()


def build_ascii_string_packet(packet_id: int, text: str) -> bytes:
    """Build a packet with ASCII/Latin-1 string (cliente Godot format).

    Args:
        packet_id: Packet ID byte
        text: Text to encode

    Returns:
        Packet bytes: packet_id + length (int16 LE) + text (latin-1)
    """
    encoded = text.encode("latin-1")
    length = len(encoded).to_bytes(2, "little")
    return bytes([packet_id]) + length + encoded


def build_godot_put_string_packet(packet_id: int, text: str) -> bytes:
    """Build a packet with Godot put_string format (int32 length + UTF-8).

    Args:
        packet_id: Packet ID byte
        text: Text to encode

    Returns:
        Packet bytes: packet_id + length (int32 LE) + text (utf-8)
    """
    encoded = text.encode("utf-8")
    length = len(encoded).to_bytes(4, "little", signed=True)  # int32 signed
    return bytes([packet_id]) + length + encoded


def create_mock_party_create_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartyCreateCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


def create_mock_party_join_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartyJoinCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


def create_mock_party_accept_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartyAcceptCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


def create_mock_party_leave_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartyLeaveCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


def create_mock_party_message_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartyMessageCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


def create_mock_party_kick_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartyKickCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


def create_mock_party_set_leader_handler(message_sender: MagicMock | None = None) -> MagicMock:
    """Crea un mock de PartySetLeaderCommandHandler."""
    handler = MagicMock()
    handler.message_sender = message_sender or MagicMock()
    handler.handle = AsyncMock()
    return handler


class TestTaskPartyCreate:
    """Test PARTY_CREATE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful party creation."""
        session_data = {"user_id": 1}

        party_create_handler = create_mock_party_create_handler(message_sender=mock_message_sender)
        party_create_handler.handle.return_value = CommandResult.ok(
            data={"party_id": 1, "message": "Party creada exitosamente"}
        )

        task = TaskPartyCreate(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_create_handler=party_create_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_create_handler.handle.assert_called_once()
        call_args = party_create_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartyCreateCommand)
        assert call_args.user_id == 1

    @pytest.mark.asyncio
    async def test_execute_failure(self, mock_message_sender):
        """Test party creation failure."""
        session_data = {"user_id": 1}

        party_create_handler = create_mock_party_create_handler(message_sender=mock_message_sender)
        party_create_handler.handle.return_value = CommandResult.error("Ya estás en una party")

        task = TaskPartyCreate(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_create_handler=party_create_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_create_handler.handle.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_message_sender):
        """Test party creation exception handling."""
        session_data = {"user_id": 1}

        party_create_handler = create_mock_party_create_handler(message_sender=mock_message_sender)
        party_create_handler.handle.return_value = CommandResult.error("Error al crear la party")

        task = TaskPartyCreate(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_create_handler=party_create_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_create_handler.handle.assert_called_once()


class TestTaskPartyJoin:
    """Test PARTY_JOIN task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful party invitation."""
        session_data = {"user_id": 1}

        party_join_handler = create_mock_party_join_handler(message_sender=mock_message_sender)
        party_join_handler.handle.return_value = CommandResult.ok(
            data={"target_username": "Player2", "message": "Player2 invitado a tu party"}
        )

        # Mock packet data with username (Godot put_string format: int32 length + UTF-8)
        data = build_godot_put_string_packet(0x5D, "Player2")

        task = TaskPartyJoin(
            data=data,
            message_sender=mock_message_sender,
            party_join_handler=party_join_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_join_handler.handle.assert_called_once()
        call_args = party_join_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartyJoinCommand)
        assert call_args.user_id == 1
        assert call_args.target_username == "Player2"

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_message_sender):
        """Test invitation with empty username."""
        session_data = {"user_id": 1}

        party_join_handler = create_mock_party_join_handler()

        # Mock packet data with empty username
        data = b"\x5d\x00\x00"

        task = TaskPartyJoin(
            data=data,
            message_sender=mock_message_sender,
            party_join_handler=party_join_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify - no debe llamar al handler con username vacío
        party_join_handler.handle.assert_not_called()


class TestTaskPartyAcceptMember:
    """Test PARTY_ACCEPT_MEMBER task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful invitation acceptance."""
        session_data = {"user_id": 2}

        party_accept_handler = create_mock_party_accept_handler(message_sender=mock_message_sender)
        party_accept_handler.handle.return_value = CommandResult.ok(
            data={"party_id": 1, "leader_username": "Leader", "message": "Te has unido a la party"}
        )

        # Mock packet data with leader username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x76, "Leader")

        task = TaskPartyAcceptMember(
            data=data,
            message_sender=mock_message_sender,
            party_accept_handler=party_accept_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_accept_handler.handle.assert_called_once()
        call_args = party_accept_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartyAcceptCommand)
        assert call_args.user_id == 2
        assert call_args.leader_username == "Leader"

    @pytest.mark.asyncio
    async def test_execute_no_invitation(self, mock_message_sender):
        """Test acceptance with no pending invitation."""
        session_data = {"user_id": 2}

        party_accept_handler = create_mock_party_accept_handler(message_sender=mock_message_sender)
        party_accept_handler.handle.return_value = CommandResult.error(
            "No tienes una invitación pendiente de Leader"
        )

        # Mock packet data (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x76, "Leader")

        task = TaskPartyAcceptMember(
            data=data,
            message_sender=mock_message_sender,
            party_accept_handler=party_accept_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_accept_handler.handle.assert_called_once()


class TestTaskPartyLeave:
    """Test PARTY_LEAVE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful party leave."""
        session_data = {"user_id": 1}

        party_leave_handler = create_mock_party_leave_handler(message_sender=mock_message_sender)
        party_leave_handler.handle.return_value = CommandResult.ok(
            data={"message": "Has abandonado la party"}
        )

        task = TaskPartyLeave(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_leave_handler=party_leave_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_leave_handler.handle.assert_called_once()
        call_args = party_leave_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartyLeaveCommand)
        assert call_args.user_id == 1

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_message_sender):
        """Test exception handling."""
        session_data = {"user_id": 1}

        party_leave_handler = create_mock_party_leave_handler(message_sender=mock_message_sender)
        party_leave_handler.handle.return_value = CommandResult.error("Error al abandonar la party")

        task = TaskPartyLeave(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_leave_handler=party_leave_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_leave_handler.handle.assert_called_once()


class TestTaskPartyMessage:
    """Test PARTY_MESSAGE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful party message."""
        session_data = {"user_id": 1}

        party_message_handler = create_mock_party_message_handler(
            message_sender=mock_message_sender
        )
        party_message_handler.handle.return_value = CommandResult.ok(
            data={"message": "Hello party!", "error": None}
        )

        # Mock packet data with message (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x60, "Hello party!")

        task = TaskPartyMessage(
            data=data,
            message_sender=mock_message_sender,
            party_message_handler=party_message_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_message_handler.handle.assert_called_once()
        call_args = party_message_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartyMessageCommand)
        assert call_args.user_id == 1
        assert call_args.message == "Hello party!"

    @pytest.mark.asyncio
    async def test_execute_empty_message(self, mock_message_sender):
        """Test party message with empty text."""
        session_data = {"user_id": 1}

        party_message_handler = create_mock_party_message_handler()

        # Mock packet data with empty message (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x60, "")

        task = TaskPartyMessage(
            data=data,
            message_sender=mock_message_sender,
            party_message_handler=party_message_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify - no debe llamar al handler con mensaje vacío
        party_message_handler.handle.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_error(self, mock_message_sender):
        """Test party message when not in party."""
        session_data = {"user_id": 1}

        party_message_handler = create_mock_party_message_handler(
            message_sender=mock_message_sender
        )
        party_message_handler.handle.return_value = CommandResult.ok(
            data={"message": "Hello", "error": "No eres miembro de ninguna party"}
        )

        # Mock packet data (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x60, "Hello")

        task = TaskPartyMessage(
            data=data,
            message_sender=mock_message_sender,
            party_message_handler=party_message_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_message_handler.handle.assert_called_once()


class TestTaskPartyKick:
    """Test PARTY_KICK task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful member kick."""
        session_data = {"user_id": 1}

        party_kick_handler = create_mock_party_kick_handler(message_sender=mock_message_sender)
        party_kick_handler.handle.return_value = CommandResult.ok(
            data={"target_username": "Player2", "message": "Player2 ha sido expulsado"}
        )

        # Mock packet data with target username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x74, "Player2")

        task = TaskPartyKick(
            data=data,
            message_sender=mock_message_sender,
            party_kick_handler=party_kick_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_kick_handler.handle.assert_called_once()
        call_args = party_kick_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartyKickCommand)
        assert call_args.user_id == 1
        assert call_args.target_username == "Player2"

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_message_sender):
        """Test kick with empty username."""
        session_data = {"user_id": 1}

        party_kick_handler = create_mock_party_kick_handler()

        # Mock packet data with empty username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x74, "")

        task = TaskPartyKick(
            data=data,
            message_sender=mock_message_sender,
            party_kick_handler=party_kick_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify - no debe llamar al handler con username vacío
        party_kick_handler.handle.assert_not_called()


class TestTaskPartySetLeader:
    """Test PARTY_SET_LEADER task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_message_sender):
        """Test successful leadership transfer."""
        session_data = {"user_id": 1}

        party_set_leader_handler = create_mock_party_set_leader_handler(
            message_sender=mock_message_sender
        )
        party_set_leader_handler.handle.return_value = CommandResult.ok(
            data={"target_username": "Player2", "message": "Liderazgo transferido a Player2"}
        )

        # Mock packet data with target username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x75, "Player2")

        task = TaskPartySetLeader(
            data=data,
            message_sender=mock_message_sender,
            party_set_leader_handler=party_set_leader_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        party_set_leader_handler.handle.assert_called_once()
        call_args = party_set_leader_handler.handle.call_args[0][0]
        assert isinstance(call_args, PartySetLeaderCommand)
        assert call_args.user_id == 1
        assert call_args.target_username == "Player2"

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_message_sender):
        """Test leadership transfer with empty username."""
        session_data = {"user_id": 1}

        party_set_leader_handler = create_mock_party_set_leader_handler()

        # Mock packet data with empty username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x75, "")

        task = TaskPartySetLeader(
            data=data,
            message_sender=mock_message_sender,
            party_set_leader_handler=party_set_leader_handler,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify - no debe llamar al handler con username vacío
        party_set_leader_handler.handle.assert_not_called()
