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


class TestTaskPartyCreate:
    """Test PARTY_CREATE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party creation."""
        # Setup
        mock_party_service.create_party.return_value = (MagicMock(), "Party creada exitosamente")

        task = TaskPartyCreate(mock_party_service, mock_message_sender)

        # Execute
        await task.execute(mock_connection, 1)

        # Verify
        mock_party_service.create_party.assert_called_once_with(1)
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Party creada exitosamente", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_failure(self, mock_party_service, mock_message_sender):
        """Test party creation failure."""
        # Setup
        mock_party_service.create_party.return_value = (None, "Ya estás en una party")

        task = TaskPartyCreate(mock_party_service, mock_message_sender)

        # Execute
        await task.execute(mock_connection, 1)

        # Verify
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Ya estás en una party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_party_service, mock_message_sender):
        """Test exception handling."""
        # Setup
        mock_party_service.create_party.side_effect = Exception("Redis error")

        task = TaskPartyCreate(mock_party_service, mock_message_sender)

        # Execute
        await task.execute(mock_connection, 1)

        # Verify error message sent
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Error al crear la party. Intenta nuevamente.", font_color=1
        )


class TestTaskPartyJoin:
    """Test PARTY_JOIN task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party invitation."""
        # Setup
        mock_party_service.invite_to_party.return_value = "Player2 invitado a tu party"

        task = TaskPartyJoin(mock_party_service, mock_message_sender)

        # Mock packet data with username
        data = b"\x5d\x00P\x00l\x00a\x00y\x00e\x00r\x002\x00\x00\x00"  # PARTY_JOIN + "Player2"

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify
        mock_party_service.invite_to_party.assert_called_once_with(1, "Player2")
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Player2 invitado a tu party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_party_service, mock_message_sender):
        """Test invitation with empty username."""
        task = TaskPartyJoin(mock_party_service, mock_message_sender)

        # Mock packet data with empty username
        data = b"\x5d\x00\x00"  # PARTY_JOIN + empty string

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un nombre de usuario" in args[1]


class TestTaskPartyAcceptMember:
    """Test PARTY_ACCEPT_MEMBER task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful invitation acceptance."""
        # Setup
        mock_invitation = MagicMock()
        mock_invitation.party_id = 1

        mock_party_service.get_user_invitations.return_value = [mock_invitation]
        mock_party_service.accept_invitation.return_value = "Te has unido a la party"

        task = TaskPartyAcceptMember(mock_party_service, mock_message_sender)

        # Mock packet data with leader username
        data = b"\x76\x00L\x00e\x00a\x00d\x00e\x00r\x00\x00\x00"  # PARTY_ACCEPT_MEMBER + "Leader"

        # Execute
        await task.execute(mock_connection, 2, data)

        # Verify
        mock_party_service.get_user_invitations.assert_called_once_with(2)
        mock_party_service.accept_invitation.assert_called_once_with(2, 1)
        mock_message_sender.send_console_msg.assert_called_once_with(
            2, "Te has unido a la party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_no_invitation(self, mock_party_service, mock_message_sender):
        """Test acceptance with no pending invitation."""
        task = TaskPartyAcceptMember(mock_party_service, mock_message_sender)

        # Mock packet data
        data = b"\x76\x00L\x00e\x00a\x00d\x00e\x00r\x00\x00\x00"

        # Setup - no invitations
        mock_party_service.get_user_invitations.return_value = []

        # Execute
        await task.execute(mock_connection, 2, data)

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "no tienes una invitación pendiente" in args[1]


class TestTaskPartyLeave:
    """Test PARTY_LEAVE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party leave."""
        # Setup
        mock_party_service.leave_party.return_value = "Has abandonado la party"

        task = TaskPartyLeave(mock_party_service, mock_message_sender)

        # Execute
        await task.execute(mock_connection, 1)

        # Verify
        mock_party_service.leave_party.assert_called_once_with(1)
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Has abandonado la party", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_exception(self, mock_party_service, mock_message_sender):
        """Test exception handling."""
        # Setup
        mock_party_service.leave_party.side_effect = Exception("Connection error")

        task = TaskPartyLeave(mock_party_service, mock_message_sender)

        # Execute
        await task.execute(mock_connection, 1)

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Error al abandonar la party. Intenta nuevamente.", font_color=1
        )


class TestTaskPartyMessage:
    """Test PARTY_MESSAGE task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful party message."""
        # Setup
        mock_party_service.send_party_message.return_value = None  # No error

        task = TaskPartyMessage(mock_party_service, mock_message_sender)

        # Mock packet data with message
        message_data = b"\x60\x00H\x00e\x00l\x00l\x00o\x00 \x00p\x00a\x00r\x00t\x00y\x00!\x00\x00\x00"

        # Execute
        await task.execute(mock_connection, 1, message_data)

        # Verify
        mock_party_service.send_party_message.assert_called_once_with(1, "Hello party!")
        # No message should be sent on success
        mock_message_sender.send_console_msg.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_empty_message(self, mock_party_service, mock_message_sender):
        """Test party message with empty text."""
        task = TaskPartyMessage(mock_party_service, mock_message_sender)

        # Mock packet data with empty message
        data = b"\x60\x00\x00"  # PARTY_MESSAGE + empty string

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un mensaje" in args[1]

    @pytest.mark.asyncio
    async def test_execute_error(self, mock_party_service, mock_message_sender):
        """Test party message when not in party."""
        # Setup
        mock_party_service.send_party_message.return_value = "No eres miembro de ninguna party"

        task = TaskPartyMessage(mock_party_service, mock_message_sender)

        # Mock packet data
        message_data = b"\x60\x00H\x00e\x00l\x00l\x00o\x00\x00\x00"

        # Execute
        await task.execute(mock_connection, 1, message_data)

        # Verify error message sent
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "No eres miembro de ninguna party", font_color=7
        )


class TestTaskPartyKick:
    """Test PARTY_KICK task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful member kick."""
        # Setup
        mock_party_service.kick_member.return_value = "Player2 ha sido expulsado"

        task = TaskPartyKick(mock_party_service, mock_message_sender)

        # Mock packet data with target username
        data = b"\x74\x00P\x00l\x00a\x00y\x00e\x00r\x002\x00\x00\x00"

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify
        mock_party_service.kick_member.assert_called_once_with(1, "Player2")
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Player2 ha sido expulsado", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_party_service, mock_message_sender):
        """Test kick with empty username."""
        task = TaskPartyKick(mock_party_service, mock_message_sender)

        # Mock packet data with empty username
        data = b"\x74\x00\x00"

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un nombre de usuario" in args[1]


class TestTaskPartySetLeader:
    """Test PARTY_SET_LEADER task handler."""

    @pytest.mark.asyncio
    async def test_execute_success(self, mock_party_service, mock_message_sender):
        """Test successful leadership transfer."""
        # Setup
        mock_party_service.transfer_leadership.return_value = "Liderazgo transferido a Player2"

        task = TaskPartySetLeader(mock_party_service, mock_message_sender)

        # Mock packet data with target username
        data = b"\x75\x00P\x00l\x00a\x00y\x00e\x00r\x002\x00\x00\x00"

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify
        mock_party_service.transfer_leadership.assert_called_once_with(1, "Player2")
        mock_message_sender.send_console_msg.assert_called_once_with(
            1, "Liderazgo transferido a Player2", font_color=7
        )

    @pytest.mark.asyncio
    async def test_execute_empty_username(self, mock_party_service, mock_message_sender):
        """Test leadership transfer with empty username."""
        task = TaskPartySetLeader(mock_party_service, mock_message_sender)

        # Mock packet data with empty username
        data = b"\x75\x00\x00"

        # Execute
        await task.execute(mock_connection, 1, data)

        # Verify error message
        mock_message_sender.send_console_msg.assert_called_once()
        args = mock_message_sender.send_console_msg.call_args[0]
        assert "Debes especificar un nombre de usuario" in args[1]
