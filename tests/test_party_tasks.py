"""Tests for Party Task Handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.tasks.task_party_accept_member import TaskPartyAcceptMember
from src.tasks.task_party_create import TaskPartyCreate
from src.tasks.task_party_join import TaskPartyJoin
from src.tasks.task_party_kick import TaskPartyKick
from src.tasks.task_party_leave import TaskPartyLeave
from src.tasks.task_party_message import TaskPartyMessage
from src.tasks.task_party_set_leader import TaskPartySetLeader


@pytest.fixture
def mock_party_service():
    """Create a mock party service."""
    return AsyncMock()


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


class TestTaskPartyCreate:
    """Test PARTY_CREATE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party creation."""
        # Setup
        mock_party_service.create_party.return_value = (MagicMock(), "Party creada exitosamente")
        session_data = {"user_id": 1}

        task = TaskPartyCreate(
            data=b"\x00",  # Packet data (no additional data needed)
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.create_party.assert_called_once()
        mock_message_sender.send_console_msg.assert_called()

    @pytest.mark.asyncio
    async def test_execute_failure(self, mock_party_service, mock_message_sender):
        """Test party creation failure."""
        # Setup
        mock_party_service.create_party.return_value = (None, "Ya estás en una party")
        session_data = {"user_id": 1}

        task = TaskPartyCreate(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Ya estás en una party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_party_service, mock_message_sender):
        """Test party creation exception handling."""
        # Setup
        mock_party_service.create_party.side_effect = Exception("Test error")
        session_data = {"user_id": 1}

        task = TaskPartyCreate(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message sent
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Error al crear la party. Intenta nuevamente.", font_color=1
        )


class TestTaskPartyJoin:
    """Test PARTY_JOIN task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party invitation."""
        # Setup
        mock_party_service.invite_to_party.return_value = "Player2 invitado a tu party"
        session_data = {"user_id": 1}

        # Mock packet data with username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x5D, "Player2")  # PARTY_JOIN + "Player2"

        task = TaskPartyJoin(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.invite_to_party.assert_called_once_with(1, "Player2")
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Player2 invitado a tu party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_party_service, mock_message_sender):
        """Test invitation with empty username."""
        session_data = {"user_id": 1}

        # Mock packet data with empty username
        data = b"\x5d\x00\x00"  # PARTY_JOIN + empty string

        task = TaskPartyJoin(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un nombre de usuario" in args[0]


class TestTaskPartyAcceptMember:
    """Test PARTY_ACCEPT_MEMBER task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful invitation acceptance."""
        # Setup
        mock_invitation = MagicMock()
        mock_invitation.party_id = 1
        mock_invitation.inviter_username = "Leader"

        mock_party_service.get_user_invitations.return_value = [mock_invitation]
        mock_party_service.accept_invitation.return_value = "Te has unido a la party"
        session_data = {"user_id": 2}

        # Mock packet data with leader username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x76, "Leader")  # PARTY_ACCEPT_MEMBER + "Leader"

        task = TaskPartyAcceptMember(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.get_user_invitations.assert_called_once_with(2)
        mock_party_service.accept_invitation.assert_called_once_with(2, 1)
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Te has unido a la party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_no_invitation(self, mock_party_service, mock_message_sender):
        """Test acceptance with no pending invitation."""
        session_data = {"user_id": 2}

        # Mock packet data (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x76, "Leader")

        # Setup - no invitations
        mock_party_service.get_user_invitations.return_value = []

        task = TaskPartyAcceptMember(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "no tienes una invitación pendiente" in args[0].lower()


class TestTaskPartyLeave:
    """Test PARTY_LEAVE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party leave."""
        # Setup
        mock_party_service.leave_party.return_value = "Has abandonado la party"
        session_data = {"user_id": 1}

        task = TaskPartyLeave(
            data=b"\x00",  # No additional data needed
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.leave_party.assert_called_once_with(1)
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Has abandonado la party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_party_service, mock_message_sender):
        """Test exception handling."""
        # Setup
        mock_party_service.leave_party.side_effect = Exception("Connection error")
        session_data = {"user_id": 1}

        task = TaskPartyLeave(
            data=b"\x00",
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Error al abandonar la party. Intenta nuevamente.", font_color=1
        )


class TestTaskPartyMessage:
    """Test PARTY_MESSAGE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party message."""
        # Setup
        mock_party_service.send_party_message.return_value = ""  # Empty string = success
        session_data = {"user_id": 1}

        # Mock packet data with message (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x60, "Hello party!")  # PARTY_MESSAGE

        task = TaskPartyMessage(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.send_party_message.assert_called_once_with(1, "Hello party!")
        # No message should be sent on success
        mock_message_sender.send_console_msg.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_empty_message(self, mock_party_service, mock_message_sender):
        """Test party message with empty text."""
        session_data = {"user_id": 1}

        # Mock packet data with empty message (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x60, "")  # PARTY_MESSAGE + empty string

        task = TaskPartyMessage(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un mensaje" in args[0]

    @pytest.mark.asyncio
    async def test_execute_error(self, mock_party_service, mock_message_sender):
        """Test party message when not in party."""
        # Setup
        mock_party_service.send_party_message.return_value = "No eres miembro de ninguna party"
        session_data = {"user_id": 1}

        # Mock packet data (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x60, "Hello")  # PARTY_MESSAGE

        task = TaskPartyMessage(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message sent
        mock_message_sender.send_console_msg.assert_called_once_with(
            "No eres miembro de ninguna party", font_color=7
        )


class TestTaskPartyKick:
    """Test PARTY_KICK task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful member kick."""
        # Setup
        mock_party_service.kick_member.return_value = "Player2 ha sido expulsado"
        session_data = {"user_id": 1}

        # Mock packet data with target username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x74, "Player2")  # PARTY_KICK

        task = TaskPartyKick(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.kick_member.assert_called_once_with(1, "Player2")
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Player2 ha sido expulsado", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_party_service, mock_message_sender):
        """Test kick with empty username."""
        session_data = {"user_id": 1}

        # Mock packet data with empty username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x74, "")  # PARTY_KICK + empty string

        task = TaskPartyKick(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un nombre de usuario" in args[0]


class TestTaskPartySetLeader:
    """Test PARTY_SET_LEADER task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful leadership transfer."""
        # Setup
        mock_party_service.transfer_leadership.return_value = "Liderazgo transferido a Player2"
        session_data = {"user_id": 1}

        # Mock packet data with target username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x75, "Player2")  # PARTY_SET_LEADER

        task = TaskPartySetLeader(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify
        mock_party_service.transfer_leadership.assert_called_once_with(1, "Player2")
        mock_message_sender.send_console_msg.assert_called_once_with(
            "Liderazgo transferido a Player2", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_party_service, mock_message_sender):
        """Test leadership transfer with empty username."""
        session_data = {"user_id": 1}

        # Mock packet data with empty username (ASCII/Latin-1 format)
        data = build_ascii_string_packet(0x75, "")  # PARTY_SET_LEADER + empty string

        task = TaskPartySetLeader(
            data=data,
            message_sender=mock_message_sender,
            party_service=mock_party_service,
            session_data=session_data,
        )

        # Execute
        await task.execute()

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un nombre de usuario" in args[0]
