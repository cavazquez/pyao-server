"""Tests for Party Service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.party_service import PartyService


@pytest.fixture
def mock_party_repo():
    """Create a mock party repository."""
    # Use MagicMock as base, then configure async methods
    repo = MagicMock()
    repo.get_user_party = AsyncMock(return_value=None)
    repo.get_next_party_id = AsyncMock(return_value=1)
    repo.save_party = AsyncMock(return_value=None)
    repo.get_invitation = AsyncMock(return_value=None)
    repo.save_invitation = AsyncMock(return_value=None)
    repo.remove_invitation = AsyncMock(return_value=None)
    repo.get_user_invitations = AsyncMock(return_value=[])
    repo.delete_party = AsyncMock()
    repo.remove_member_from_party = AsyncMock()
    repo.get_party = AsyncMock(return_value=None)
    repo.update_party_metadata = AsyncMock()
    repo.update_member = AsyncMock()
    return repo


@pytest.fixture
def mock_player_repo():
    """Create a mock player repository."""
    # Use MagicMock as base, then configure async methods
    repo = MagicMock()

    # Mock get_stats to return a dict with proper values
    repo.get_stats = AsyncMock(
        return_value={
            "level": 20,
            "min_hp": 100,  # Current HP
            "max_hp": 100,
        }
    )

    # Mock helper methods
    repo.get_level = AsyncMock(return_value=20)
    repo.get_current_hp = AsyncMock(return_value=100)
    repo.is_alive = AsyncMock(return_value=True)

    # Mock get_charisma to return charisma value
    repo.get_charisma = AsyncMock(return_value=18)

    # Mock get_skills to return leadership skill
    repo.get_skills = AsyncMock(
        return_value={
            "liderazgo": 10,  # 18 * 10 = 180 >= 100
        }
    )

    # Mock get_attributes for username lookup (returns dict with username)
    repo.get_attributes = AsyncMock(return_value={"username": "TestUser"})

    return repo


@pytest.fixture
def mock_message_sender():
    """Create a mock message sender."""
    # MessageSender is a sync object with async methods
    sender = MagicMock()
    sender.send_console_msg = AsyncMock(return_value=None)
    return sender


@pytest.fixture
def mock_broadcast_service():
    """Create a mock broadcast service."""
    # BroadcastService has async methods, but the object itself is sync
    return MagicMock()


@pytest.fixture
def mock_account_repo():
    """Create a mock account repository."""
    # Use MagicMock as base, then configure async methods
    repo = MagicMock()
    repo.get_account_by_user_id = AsyncMock(return_value={"username": "TestUser"})
    return repo


@pytest.fixture
def mock_map_manager():
    """Create a mock map manager."""
    manager = MagicMock()
    # Mock _players_by_map for player search
    # _players_by_map stores (MessageSender, username) tuples
    # MessageSender is sync but has async methods
    mock_sender_for_map = MagicMock()
    mock_sender_for_map.send_console_msg = AsyncMock()
    manager._players_by_map = {
        1: {  # map_id 1
            2: (mock_sender_for_map, "Player2"),  # user_id 2 with username
        }
    }
    # Mock new public methods
    manager.get_all_online_players.return_value = [(2, "Player2", 1)]
    manager.find_player_by_username.return_value = 2
    # get_player_message_sender is sync, but returns MessageSender which has async methods
    mock_sender = MagicMock()
    mock_sender.send_console_msg = AsyncMock()
    manager.get_player_message_sender.return_value = mock_sender
    manager.get_player_username.return_value = "Player1"
    manager.get_maps_with_players.return_value = [1]
    return manager


@pytest.fixture
def party_service(
    mock_party_repo,
    mock_player_repo,
    mock_message_sender,
    mock_broadcast_service,
    mock_map_manager,
    mock_account_repo,
):
    """Create a party service with mocked dependencies."""
    return PartyService(
        mock_party_repo,
        mock_player_repo,
        mock_message_sender,
        mock_broadcast_service,
        mock_map_manager,
        mock_account_repo,
    )


class TestPartyCreation:
    """Test party creation functionality."""

    @pytest.mark.asyncio
    async def test_can_create_party_success(self, party_service):
        """Test successful party creation check."""
        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is True
        assert not error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_low_level(self, party_service, mock_player_repo):
        """Test party creation fails with low level."""
        # Configure mocks for low level player (level 0, below MIN_LEVEL_TO_CREATE which is 1)
        mock_player_repo.get_stats = AsyncMock(
            return_value={
                "level": 0,  # Below MIN_LEVEL_TO_CREATE (1)
                "min_hp": 100,
                "max_hp": 100,
            }
        )
        mock_player_repo.get_level = AsyncMock(return_value=0)  # Use helper method
        mock_player_repo.get_charisma = AsyncMock(return_value=18)
        mock_player_repo.get_skills = AsyncMock(
            return_value={
                "liderazgo": 10,
            }
        )

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "Debes ser nivel 1" in error_msg or "nivel 1" in error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_dead(self, party_service, mock_player_repo):
        """Test party creation fails when dead."""
        # Configure mocks for dead player
        mock_player_repo.get_stats = AsyncMock(
            return_value={
                "level": 20,
                "min_hp": 0,  # Dead
                "max_hp": 100,
            }
        )
        mock_player_repo.get_level = AsyncMock(return_value=20)
        mock_player_repo.get_current_hp = AsyncMock(return_value=0)
        mock_player_repo.is_alive = AsyncMock(return_value=False)  # Use helper method
        mock_player_repo.get_charisma = AsyncMock(return_value=18)

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "muerto" in error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_insufficient_leadership(
        self, party_service, mock_player_repo
    ):
        """Test party creation fails with insufficient leadership."""
        # Configure mocks for insufficient leadership (5 * 10 = 50 < 100)
        mock_player_repo.get_stats = AsyncMock(
            return_value={
                "level": 20,
                "min_hp": 100,
                "max_hp": 100,
            }
        )
        mock_player_repo.get_charisma = AsyncMock(return_value=5)  # 5 * 10 = 50 < 100
        mock_player_repo.get_skills = AsyncMock(
            return_value={
                "liderazgo": 10,  # 5 * 10 = 50 < 100
            }
        )

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "Carisma * Liderazgo" in error_msg or "carisma" in error_msg.lower()
        assert "50" in error_msg  # 5 * 10 = 50

    @pytest.mark.asyncio
    async def test_create_party_success(self, party_service, mock_party_repo):
        """Test successful party creation."""
        party, message = await party_service.create_party(1)

        assert party is not None
        assert party.party_id == 1
        assert party.leader_id == 1
        assert party.leader_username == "Player1"
        assert "formado una party" in message.lower()

        # Verify repository calls
        mock_party_repo.get_next_party_id.assert_called_once()
        mock_party_repo.save_party.assert_called_once()


class TestPartyInvitation:
    """Test party invitation functionality."""

    @pytest.mark.asyncio
    async def test_invite_to_party_success(self, party_service, mock_party_repo, mock_player_repo):
        """Test successful party invitation."""
        # Mock party exists and user is leader
        mock_party = MagicMock()
        mock_party.is_full = False
        mock_party.is_member.return_value = False
        mock_party.can_join_by_level = MagicMock(return_value=True)
        mock_party.party_id = 1
        mock_party.is_leader.return_value = True

        # Configure get_user_party to return party for inviter (1) and None for target (2)
        def get_user_party_side_effect(user_id):
            if user_id == 1:
                return mock_party
            return None

        mock_party_repo.get_user_party.side_effect = get_user_party_side_effect

        # Configure player stats for target
        mock_player_repo.get_stats = AsyncMock(
            return_value={
                "level": 20,
                "min_hp": 100,
            }
        )

        message = await party_service.invite_to_party(1, "Player2")

        assert "invitado" in message.lower() or "invitación" in message.lower()
        mock_party_repo.save_invitation.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_invite_no_party(self, party_service, mock_party_repo):
        """Test invitation fails when inviter has no party."""
        mock_party_repo.get_user_party = AsyncMock(return_value=None)

        message = await party_service.invite_to_party(1, "Player2")

        assert "no eres miembro" in message.lower()

    @pytest.mark.asyncio
    async def test_cannot_invite_not_leader(self, party_service, mock_party_repo):
        """Test invitation fails when inviter is not leader."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = False

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)

        message = await party_service.invite_to_party(1, "Player2")

        assert "solo el líder" in message.lower()


class TestPartyAcceptance:
    """Test party acceptance functionality."""

    @pytest.mark.asyncio
    async def test_accept_invitation_success(
        self, party_service, mock_party_repo, mock_player_repo
    ):
        """Test successful invitation acceptance."""
        # Mock invitation exists
        mock_invitation = MagicMock()
        mock_invitation.is_expired = False
        mock_invitation.party_id = 1

        mock_party_repo.get_invitation = AsyncMock(return_value=mock_invitation)
        # Ensure get_attributes returns a valid dict for username lookup
        mock_player_repo.get_attributes = AsyncMock(return_value={"username": "TestUser"})

        # Mock party exists and can accept
        mock_party = MagicMock()
        mock_party.is_full = False
        mock_party.add_member.return_value = True
        mock_party.member_ids = {1, 2}

        mock_party_repo.get_party = AsyncMock(return_value=mock_party)
        mock_party_repo.get_user_invitations = AsyncMock(return_value=[mock_invitation])

        message = await party_service.accept_invitation(2, 1)

        assert "te has unido" in message.lower()
        mock_party_repo.save_party.assert_called_once()
        mock_party_repo.remove_invitation.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_accept_no_invitation(self, party_service, mock_party_repo):
        """Test acceptance fails when no invitation exists."""
        mock_party_repo.get_invitation = AsyncMock(return_value=None)

        message = await party_service.accept_invitation(2, 1)

        assert "no tienes una invitación" in message.lower()


class TestPartyLeaving:
    """Test party leaving functionality."""

    @pytest.mark.asyncio
    async def test_leave_party_as_member(self, party_service, mock_party_repo, mock_map_manager):
        """Test leaving party as regular member."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = False
        mock_party.remove_member.return_value = MagicMock()
        mock_party.member_count = 2
        mock_party.member_ids = {1, 2}  # Set member IDs so the loop can iterate
        # Mock get_member to return a member with username
        mock_member = MagicMock()
        mock_member.username = "TestUser"
        mock_party.get_member.return_value = mock_member

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)
        mock_party_repo.save_party = AsyncMock()
        mock_party_repo.remove_member_from_party = AsyncMock()

        # Ensure get_player_message_sender returns a properly configured mock
        mock_sender = MagicMock()
        mock_sender.send_console_msg = AsyncMock()
        mock_map_manager.get_player_message_sender.return_value = mock_sender

        message = await party_service.leave_party(2)

        assert "abandonado la party" in message.lower()
        mock_party_repo.save_party.assert_called_once()
        mock_party_repo.remove_member_from_party.assert_called_once()

    @pytest.mark.asyncio
    async def test_leave_party_as_leader_disbands(self, party_service, mock_party_repo):
        """Test leaving party as leader disbands party."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = True
        mock_party.member_ids = {1, 2, 3}
        mock_party.party_id = 1

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)
        mock_party_repo.delete_party = AsyncMock()

        message = await party_service.leave_party(1)

        assert "disuelto" in message.lower()
        mock_party_repo.delete_party.assert_called_once()


class TestPartyManagement:
    """Test party management functionality."""

    @pytest.mark.asyncio
    async def test_kick_member_success(self, party_service, mock_party_repo):
        """Test successful member kick."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = True
        mock_party.is_member.return_value = True
        mock_party.remove_member.return_value = MagicMock()
        mock_party.member_count = 3

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)

        message = await party_service.kick_member(1, "Player2")

        assert "expulsado" in message.lower()
        mock_party_repo.save_party.assert_called_once()

    @pytest.mark.asyncio
    async def test_transfer_leadership_success(self, party_service, mock_party_repo):
        """Test successful leadership transfer."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = True
        mock_party.is_member.return_value = True
        mock_party.transfer_leadership.return_value = True

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)

        message = await party_service.transfer_leadership(1, "Player2")

        assert "transferido" in message.lower()
        mock_party_repo.save_party.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_party_message_success(
        self, party_service, mock_party_repo, mock_map_manager, mock_account_repo
    ):
        """Test successful party message sending."""
        mock_party = MagicMock()
        mock_party.member_ids = {1, 2, 3}

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)

        # Mock message senders for each member
        # get_player_message_sender is sync, but returns MessageSender which has async methods
        mock_sender_1 = MagicMock()
        mock_sender_1.send_console_msg = AsyncMock()
        mock_sender_2 = MagicMock()
        mock_sender_2.send_console_msg = AsyncMock()
        mock_sender_3 = MagicMock()
        mock_sender_3.send_console_msg = AsyncMock()
        mock_map_manager.get_player_message_sender.side_effect = [
            mock_sender_1,
            mock_sender_2,
            mock_sender_3,
        ]

        mock_account_repo.get_account_by_user_id = AsyncMock(return_value={"username": "TestUser"})

        result = await party_service.send_party_message(1, "Hello party!")

        assert not result  # No error message
        # Verify message was sent to all members
        assert mock_sender_1.send_console_msg.called
        assert mock_sender_2.send_console_msg.called
        assert mock_sender_3.send_console_msg.called

    @pytest.mark.asyncio
    async def test_send_party_message_no_party(self, party_service, mock_party_repo):
        """Test party message fails when not in party."""
        mock_party_repo.get_user_party = AsyncMock(return_value=None)

        result = await party_service.send_party_message(1, "Hello party!")

        assert "no eres miembro" in result.lower()


class TestExperienceDistribution:
    """Test experience distribution functionality."""

    @pytest.mark.asyncio
    async def test_distribute_experience_success(self, party_service, mock_party_repo):
        """Test successful experience distribution."""
        mock_party = MagicMock()
        # distribute_experience is now async, so we need AsyncMock
        mock_party.distribute_experience = AsyncMock(return_value={2: 50.0, 3: 50.0})
        mock_party.get_member.side_effect = lambda user_id: MagicMock(
            user_id=user_id, accumulated_exp=50.0
        )

        mock_party_repo.get_user_party = AsyncMock(return_value=mock_party)

        distributed = await party_service.distribute_experience(1, 100, 1, 10, 10)

        assert distributed == {2: 50.0, 3: 50.0}
        mock_party_repo.update_party_metadata.assert_called_once()
