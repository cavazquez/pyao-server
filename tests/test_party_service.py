"""Tests for Party Service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.party_service import PartyService


@pytest.fixture
def mock_party_repo():
    """Create a mock party repository."""
    repo = AsyncMock()
    repo.get_user_party.return_value = None
    repo.get_next_party_id.return_value = 1
    repo.save_party.return_value = None
    repo.get_invitation.return_value = None
    repo.save_invitation.return_value = None
    repo.remove_invitation.return_value = None
    repo.get_user_invitations.return_value = []
    return repo


@pytest.fixture
def mock_player_repo():
    """Create a mock player repository."""
    repo = AsyncMock()

    # Mock get_stats to return a dict with proper values
    repo.get_stats.return_value = {
        "level": 20,
        "min_hp": 100,  # Current HP
        "max_hp": 100,
    }

    # Mock get_attributes to return a dict with charisma and leadership
    repo.get_attributes.return_value = {
        "charisma": 18,
        "leadership": 10,
        "username": "TestPlayer",
    }

    return repo


@pytest.fixture
def mock_message_sender():
    """Create a mock message sender."""
    sender = AsyncMock()
    sender.send_console_msg.return_value = None
    return sender


@pytest.fixture
def mock_broadcast_service():
    """Create a mock broadcast service."""
    return AsyncMock()


@pytest.fixture
def mock_map_manager():
    """Create a mock map manager."""
    manager = AsyncMock()
    # Mock _players_by_map for player search
    manager._players_by_map = {
        1: {  # map_id 1
            2: (AsyncMock(), "Player2"),  # user_id 2 with username
        }
    }
    return manager


@pytest.fixture
def party_service(
    mock_party_repo, mock_player_repo, mock_message_sender, mock_broadcast_service, mock_map_manager
):
    """Create a party service with mocked dependencies."""
    return PartyService(
        mock_party_repo,
        mock_player_repo,
        mock_message_sender,
        mock_broadcast_service,
        mock_map_manager,
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
        # Configure mocks for low level player
        mock_player_repo.get_stats.return_value = {
            "level": 10,  # Below MIN_LEVEL_TO_CREATE (15)
            "min_hp": 100,
            "max_hp": 100,
        }
        mock_player_repo.get_attributes.return_value = {
            "charisma": 18,
            "leadership": 10,
            "username": "TestPlayer",
        }

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "Debes ser nivel 15" in error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_dead(self, party_service, mock_player_repo):
        """Test party creation fails when dead."""
        # Configure mocks for dead player
        mock_player_repo.get_stats.return_value = {
            "level": 20,
            "min_hp": 0,  # Dead
            "max_hp": 100,
        }
        mock_player_repo.get_attributes.return_value = {
            "charisma": 18,
            "leadership": 10,
            "username": "TestPlayer",
        }

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "muerto" in error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_insufficient_leadership(
        self, party_service, mock_player_repo
    ):
        """Test party creation fails with insufficient leadership."""
        # Configure mocks for insufficient leadership (5 * 10 = 50 < 100)
        mock_player_repo.get_stats.return_value = {
            "level": 20,
            "min_hp": 100,
            "max_hp": 100,
        }
        mock_player_repo.get_attributes.return_value = {
            "charisma": 5,  # 5 * 10 = 50 < MIN_CHARISMA_LEADERSHIP (100)
            "leadership": 10,
            "username": "TestPlayer",
        }

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "carisma y liderazgo" in error_msg

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
        mock_party._can_join_by_level = MagicMock(return_value=True)
        mock_party.party_id = 1
        mock_party.is_leader.return_value = True

        # Configure get_user_party to return party for inviter (1) and None for target (2)
        def get_user_party_side_effect(user_id):
            if user_id == 1:
                return mock_party
            return None

        mock_party_repo.get_user_party.side_effect = get_user_party_side_effect

        # Configure player stats for target
        mock_player_repo.get_stats.return_value = {
            "level": 20,
            "min_hp": 100,
        }

        message = await party_service.invite_to_party(1, "Player2")

        assert "invitado" in message.lower() or "invitación" in message.lower()
        mock_party_repo.save_invitation.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_invite_no_party(self, party_service, mock_party_repo):
        """Test invitation fails when inviter has no party."""
        mock_party_repo.get_user_party.return_value = None

        message = await party_service.invite_to_party(1, "Player2")

        assert "no eres miembro" in message.lower()

    @pytest.mark.asyncio
    async def test_cannot_invite_not_leader(self, party_service, mock_party_repo):
        """Test invitation fails when inviter is not leader."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = False

        mock_party_repo.get_user_party.return_value = mock_party

        message = await party_service.invite_to_party(1, "Player2")

        assert "solo el líder" in message.lower()


class TestPartyAcceptance:
    """Test party acceptance functionality."""

    @pytest.mark.asyncio
    async def test_accept_invitation_success(self, party_service, mock_party_repo):
        """Test successful invitation acceptance."""
        # Mock invitation exists
        mock_invitation = MagicMock()
        mock_invitation.is_expired = False
        mock_invitation.party_id = 1

        mock_party_repo.get_invitation.return_value = mock_invitation

        # Mock party exists and can accept
        mock_party = MagicMock()
        mock_party.is_full = False
        mock_party.add_member.return_value = True
        mock_party.member_ids = {1, 2}

        mock_party_repo.get_party.return_value = mock_party
        mock_party_repo.get_user_invitations.return_value = [mock_invitation]

        message = await party_service.accept_invitation(2, 1)

        assert "te has unido" in message.lower()
        mock_party_repo.save_party.assert_called_once()
        mock_party_repo.remove_invitation.assert_called_once()

    @pytest.mark.asyncio
    async def test_cannot_accept_no_invitation(self, party_service, mock_party_repo):
        """Test acceptance fails when no invitation exists."""
        mock_party_repo.get_invitation.return_value = None

        message = await party_service.accept_invitation(2, 1)

        assert "no tienes una invitación" in message.lower()


class TestPartyLeaving:
    """Test party leaving functionality."""

    @pytest.mark.asyncio
    async def test_leave_party_as_member(self, party_service, mock_party_repo):
        """Test leaving party as regular member."""
        mock_party = MagicMock()
        mock_party.is_leader.return_value = False
        mock_party.remove_member.return_value = MagicMock()
        mock_party.member_count = 2

        mock_party_repo.get_user_party.return_value = mock_party

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

        mock_party_repo.get_user_party.return_value = mock_party

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

        mock_party_repo.get_user_party.return_value = mock_party

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

        mock_party_repo.get_user_party.return_value = mock_party

        message = await party_service.transfer_leadership(1, "Player2")

        assert "transferido" in message.lower()
        mock_party_repo.save_party.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_party_message_success(self, party_service, mock_party_repo):
        """Test successful party message sending."""
        mock_party = MagicMock()
        mock_party.member_ids = {1, 2, 3}

        mock_party_repo.get_user_party.return_value = mock_party

        result = await party_service.send_party_message(1, "Hello party!")

        assert not result  # No error message
        # MessageSender should be called for each member
        assert party_service.message_sender.send_console_msg.call_count == 3

    @pytest.mark.asyncio
    async def test_send_party_message_no_party(self, party_service, mock_party_repo):
        """Test party message fails when not in party."""
        mock_party_repo.get_user_party.return_value = None

        result = await party_service.send_party_message(1, "Hello party!")

        assert "no eres miembro" in result.lower()


class TestExperienceDistribution:
    """Test experience distribution functionality."""

    @pytest.mark.asyncio
    async def test_distribute_experience_success(self, party_service, mock_party_repo):
        """Test successful experience distribution."""
        mock_party = MagicMock()
        mock_party.distribute_experience.return_value = {2: 50.0, 3: 50.0}
        mock_party.get_member.side_effect = lambda user_id: MagicMock(
            user_id=user_id, accumulated_exp=50.0
        )

        mock_party_repo.get_user_party.return_value = mock_party

        distributed = await party_service.distribute_experience(1, 100, 1, 10, 10)

        assert distributed == {2: 50.0, 3: 50.0}
        mock_party_repo.update_party_metadata.assert_called_once()
