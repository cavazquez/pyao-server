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

    # Mock player data
    def get_player_side_effect(user_id):
        player = MagicMock()
        player.user_id = user_id
        player.username = f"Player{user_id}"
        player.level = 20
        player.is_dead = False
        player.stats = {"charisma": 10}
        player.skills = {"leadership": 10}
        return player

    repo.get_player.side_effect = get_player_side_effect
    repo.get_player_by_username.side_effect = lambda username: MagicMock(
        user_id=int(username.replace("Player", "")),
        username=username,
        level=20,
        is_dead=False,
        stats={"charisma": 10},
        skills={"leadership": 10}
    )
    return repo


@pytest.fixture
def mock_message_sender():
    """Create a mock message sender."""
    sender = AsyncMock()
    sender.send_console_msg.return_value = None
    return sender


@pytest.fixture
def party_service(mock_party_repo, mock_player_repo, mock_message_sender):
    """Create a party service with mocked dependencies."""
    return PartyService(mock_party_repo, mock_player_repo, mock_message_sender)


class TestPartyCreation:
    """Test party creation functionality."""

    @pytest.mark.asyncio
    async def test_can_create_party_success(self, party_service, mock_player_repo):
        """Test successful party creation check."""
        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is True
        assert error_msg == ""

    @pytest.mark.asyncio
    async def test_cannot_create_party_low_level(self, party_service, mock_player_repo):
        """Test party creation fails with low level."""
        mock_player_repo.get_player.side_effect = lambda user_id: MagicMock(
            user_id=user_id,
            username=f"Player{user_id}",
            level=10,  # Below MIN_LEVEL_TO_CREATE (15)
            is_dead=False,
            stats={"charisma": 10},
            skills={"leadership": 10}
        )

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "Debes ser nivel 15" in error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_dead(self, party_service, mock_player_repo):
        """Test party creation fails when dead."""
        mock_player_repo.get_player.side_effect = lambda user_id: MagicMock(
            user_id=user_id,
            username=f"Player{user_id}",
            level=20,
            is_dead=True,
            stats={"charisma": 10},
            skills={"leadership": 10}
        )

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "Estás muerto" in error_msg

    @pytest.mark.asyncio
    async def test_cannot_create_party_insufficient_leadership(self, party_service, mock_player_repo):
        """Test party creation fails with insufficient leadership."""
        mock_player_repo.get_player.side_effect = lambda user_id: MagicMock(
            user_id=user_id,
            username=f"Player{user_id}",
            level=20,
            is_dead=False,
            stats={"charisma": 5},  # 5 * 10 = 50 < 100
            skills={"leadership": 10}
        )

        can_create, error_msg = await party_service.can_create_party(1)

        assert can_create is False
        assert "carisma y liderazgo" in error_msg

    @pytest.mark.asyncio
    async def test_create_party_success(self, party_service, mock_party_repo, mock_player_repo):
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
        mock_party._can_join_by_level.return_value = True
        mock_party.party_id = 1

        mock_party_repo.get_user_party.return_value = mock_party

        message = await party_service.invite_to_party(1, "Player2")

        assert "invitado a tu party" in message.lower()
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
    async def test_accept_invitation_success(self, party_service, mock_party_repo, mock_player_repo):
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
    async def test_kick_member_success(self, party_service, mock_party_repo, mock_player_repo):
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
    async def test_transfer_leadership_success(self, party_service, mock_party_repo, mock_player_repo):
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

        assert result == ""  # No error message
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
