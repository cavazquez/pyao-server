"""Tests for Party Repository."""

import json
from time import time
from unittest.mock import AsyncMock

import pytest

from src.models.party import Party, PartyInvitation, PartyMember
from src.repositories.party_repository import PartyRepository


@pytest.fixture
def mock_redis():
    """Create a mock Redis client."""
    from unittest.mock import MagicMock  # noqa: PLC0415

    mock = AsyncMock()
    # Configure pipeline to return a synchronous mock with async execute
    mock_pipeline = MagicMock()
    mock_pipeline.execute = AsyncMock(return_value=None)
    mock_pipeline.hset = MagicMock(return_value=mock_pipeline)
    mock_pipeline.set = MagicMock(return_value=mock_pipeline)
    mock_pipeline.sadd = MagicMock(return_value=mock_pipeline)
    mock_pipeline.srem = MagicMock(return_value=mock_pipeline)
    mock_pipeline.hdel = MagicMock(return_value=mock_pipeline)
    mock_pipeline.delete = MagicMock(return_value=mock_pipeline)
    mock.redis.pipeline = MagicMock(return_value=mock_pipeline)
    return mock


@pytest.fixture
def party_repository(mock_redis):
    """Create a party repository with mocked Redis."""
    return PartyRepository(mock_redis)


class TestPartyRepository:
    """Test PartyRepository functionality."""

    @pytest.mark.asyncio
    async def test_initialize(self, party_repository, mock_redis):
        """Test repository initialization."""
        mock_redis.redis.exists.return_value = False

        await party_repository.initialize()

        mock_redis.redis.set.assert_called_once_with("party:next_id", 1)

    @pytest.mark.asyncio
    async def test_get_next_party_id(self, party_repository, mock_redis):
        """Test getting next party ID."""
        mock_redis.redis.incr.return_value = 5

        party_id = await party_repository.get_next_party_id()

        assert party_id == 5
        mock_redis.redis.incr.assert_called_once_with("party:next_id")

    @pytest.mark.asyncio
    async def test_save_party(self, party_repository, mock_redis):
        """Test saving a party."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        party.add_member(2, "Member2", 20)

        await party_repository.save_party(party)

        # Verify Redis calls
        assert mock_redis.redis.pipeline.called

        # Get the pipeline and verify calls
        pipeline = mock_redis.redis.pipeline.return_value
        pipeline.hset.assert_called()
        pipeline.set.assert_called()
        pipeline.sadd.assert_called()
        pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_party_exists(self, party_repository, mock_redis):
        """Test getting an existing party."""
        # Mock party data
        party_data = {
            "party_id": 1,
            "leader_id": 1,
            "leader_username": "Leader",
            "created_at": 1234567890,
            "total_exp_earned": 100,
            "sum_elevated_levels": 1000,
            "member_count": 2,
        }

        member_data = {
            "1": json.dumps(
                {
                    "user_id": 1,
                    "username": "Leader",
                    "level": 20,
                    "accumulated_exp": 50,
                    "is_online": True,
                    "last_seen": 1234567890,
                }
            ),
            "2": json.dumps(
                {
                    "user_id": 2,
                    "username": "Member2",
                    "level": 20,
                    "accumulated_exp": 50,
                    "is_online": True,
                    "last_seen": 1234567890,
                }
            ),
        }

        mock_redis.redis.get.return_value = json.dumps(party_data)
        mock_redis.redis.hgetall.return_value = member_data

        party = await party_repository.get_party(1)

        assert party is not None
        assert party.party_id == 1
        assert party.leader_id == 1
        assert party.leader_username == "Leader"
        assert party.member_count == 2
        assert 1 in party.member_ids
        assert 2 in party.member_ids

    @pytest.mark.asyncio
    async def test_get_party_not_exists(self, party_repository, mock_redis):
        """Test getting a non-existent party."""
        mock_redis.redis.get.return_value = None

        party = await party_repository.get_party(999)

        assert party is None

    @pytest.mark.asyncio
    async def test_get_user_party(self, party_repository, mock_redis):
        """Test getting user's current party."""
        # Mock user has party ID 1
        mock_redis.redis.get.return_value = b"1"

        # Mock party data
        party_data = {
            "party_id": 1,
            "leader_id": 1,
            "leader_username": "Leader",
            "created_at": 1234567890,
            "total_exp_earned": 0,
            "sum_elevated_levels": 400,
            "member_count": 1,
        }

        member_data = {
            "1": json.dumps(
                {
                    "user_id": 1,
                    "username": "Leader",
                    "level": 20,
                    "accumulated_exp": 0,
                    "is_online": True,
                    "last_seen": 1234567890,
                }
            )
        }

        def mock_get(key):
            if key == "user:1:party":
                return b"1"
            if key == "party:1":
                return json.dumps(party_data).encode()
            return None

        def mock_hgetall(key):
            if key == "party:1:members":
                return member_data
            return {}

        mock_redis.redis.get.side_effect = mock_get
        mock_redis.redis.hgetall.side_effect = mock_hgetall

        party = await party_repository.get_user_party(1)

        assert party is not None
        assert party.party_id == 1
        assert party.leader_id == 1

    @pytest.mark.asyncio
    async def test_get_user_party_no_party(self, party_repository, mock_redis):
        """Test getting party for user not in any party."""
        mock_redis.redis.get.return_value = None

        party = await party_repository.get_user_party(1)

        assert party is None

    @pytest.mark.asyncio
    async def test_delete_party(self, party_repository, mock_redis):
        """Test deleting a party."""
        # Mock party members
        members_json = {
            "1": json.dumps({"user_id": 1, "username": "Leader"}),
            "2": json.dumps({"user_id": 2, "username": "Member2"}),
        }

        mock_redis.redis.hgetall.return_value = members_json

        await party_repository.delete_party(1)

        # Verify cleanup calls
        pipeline = mock_redis.redis.pipeline.return_value
        pipeline.delete.assert_called()
        pipeline.hdel.assert_called()
        pipeline.srem.assert_called()
        pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_member(self, party_repository, mock_redis):
        """Test updating a party member."""
        member = PartyMember(user_id=1, username="Leader", level=25, accumulated_exp=100)

        await party_repository.update_member(1, member)

        expected_data = json.dumps(
            {
                "user_id": 1,
                "username": "Leader",
                "level": 25,
                "accumulated_exp": 100,
                "is_online": True,
                "last_seen": member.last_seen,
            }
        )

        mock_redis.redis.hset.assert_called_once_with("party:1:members", "1", expected_data)

    @pytest.mark.asyncio
    async def test_add_member_to_party(self, party_repository, mock_redis):
        """Test adding a member to existing party."""
        member = PartyMember(user_id=2, username="Member2", level=20)

        # Mock existing party data
        party_data = {
            "party_id": 1,
            "leader_id": 1,
            "leader_username": "Leader",
            "created_at": 1234567890,
            "total_exp_earned": 0,
            "sum_elevated_levels": 400,
            "member_count": 1,
        }

        mock_redis.redis.get.return_value = json.dumps(party_data)

        await party_repository.add_member_to_party(1, member)

        # Verify member added and user party reference updated
        pipeline = mock_redis.redis.pipeline.return_value
        pipeline.hset.assert_called()
        pipeline.set.assert_called()
        pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_member_from_party(self, party_repository, mock_redis):
        """Test removing a member from party."""
        await party_repository.remove_member_from_party(1, 2)

        pipeline = mock_redis.redis.pipeline.return_value
        pipeline.hdel.assert_called_once_with("party:1:members", "2")
        pipeline.delete.assert_called_once_with("user:2:party")
        pipeline.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_all_parties(self, party_repository, mock_redis):
        """Test getting all party IDs."""
        mock_redis.redis.smembers.return_value = {b"1", b"2", b"3"}

        party_ids = await party_repository.get_all_parties()

        assert sorted(party_ids) == [1, 2, 3]
        mock_redis.redis.smembers.assert_called_once_with("party:index")

    @pytest.mark.asyncio
    async def test_get_party_count(self, party_repository, mock_redis):
        """Test getting total party count."""
        mock_redis.redis.scard.return_value = 5

        count = await party_repository.get_party_count()

        assert count == 5
        mock_redis.redis.scard.assert_called_once_with("party:index")

    @pytest.mark.asyncio
    async def test_save_invitation(self, party_repository, mock_redis):
        """Test saving a party invitation."""
        invitation = PartyInvitation(
            party_id=1,
            inviter_id=1,
            inviter_username="Leader",
            target_id=2,
            target_username="Target",
        )

        await party_repository.save_invitation(invitation)

        expected_data = json.dumps(
            {
                "party_id": 1,
                "inviter_id": 1,
                "inviter_username": "Leader",
                "target_id": 2,
                "target_username": "Target",
                "created_at": invitation.created_at,
            }
        )

        mock_redis.redis.hset.assert_called_once_with("party_invitations:2", "1", expected_data)

    @pytest.mark.asyncio
    async def test_get_invitation_exists(self, party_repository, mock_redis):
        """Test getting an existing invitation."""
        invitation_data = {
            "party_id": 1,
            "inviter_id": 1,
            "inviter_username": "Leader",
            "target_id": 2,
            "target_username": "Target",
            "created_at": 1234567890,
        }

        mock_redis.redis.hget.return_value = json.dumps(invitation_data)

        invitation = await party_repository.get_invitation(2, 1)

        assert invitation is not None
        assert invitation.party_id == 1
        assert invitation.inviter_id == 1
        assert invitation.target_id == 2

    @pytest.mark.asyncio
    async def test_get_invitation_not_exists(self, party_repository, mock_redis):
        """Test getting a non-existent invitation."""
        mock_redis.redis.hget.return_value = None

        invitation = await party_repository.get_invitation(2, 1)

        assert invitation is None

    @pytest.mark.asyncio
    async def test_get_user_invitations(self, party_repository, mock_redis):
        """Test getting all invitations for a user."""
        # Create fresh and expired invitations
        fresh_invitation = {
            "party_id": 1,
            "inviter_id": 1,
            "inviter_username": "Leader1",
            "target_id": 2,
            "target_username": "Target",
            "created_at": time() - 10,  # 10 seconds ago (fresh)
        }

        expired_invitation = {
            "party_id": 2,
            "inviter_id": 3,
            "inviter_username": "Leader2",
            "target_id": 2,
            "target_username": "Target",
            "created_at": time() - 35,  # 35 seconds ago (expired)
        }

        invitations_json = {"1": json.dumps(fresh_invitation), "2": json.dumps(expired_invitation)}

        mock_redis.redis.hgetall.return_value = invitations_json

        invitations = await party_repository.get_user_invitations(2)

        # Should only return fresh invitation
        assert len(invitations) == 1
        assert invitations[0].party_id == 1

        # Expired invitation should be removed
        mock_redis.redis.hdel.assert_called_once_with("party_invitations:2", "2")

    @pytest.mark.asyncio
    async def test_remove_invitation(self, party_repository, mock_redis):
        """Test removing a specific invitation."""
        await party_repository.remove_invitation(2, 1)

        mock_redis.redis.hdel.assert_called_once_with("party_invitations:2", "1")

    @pytest.mark.asyncio
    async def test_clear_user_invitations(self, party_repository, mock_redis):
        """Test clearing all invitations for a user."""
        await party_repository.clear_user_invitations(2)

        mock_redis.redis.delete.assert_called_once_with("party_invitations:2")

    @pytest.mark.asyncio
    async def test_update_party_metadata(self, party_repository, mock_redis):
        """Test updating party metadata."""
        party = Party(party_id=1, leader_id=1, leader_username="Leader")
        party.total_exp_earned = 500

        await party_repository.update_party_metadata(party)

        expected_data = json.dumps(
            {
                "party_id": 1,
                "leader_id": 1,
                "leader_username": "Leader",
                "created_at": party.created_at,
                "total_exp_earned": 500,
                "sum_elevated_levels": party.sum_elevated_levels,
                "member_count": party.member_count,
            }
        )

        pipeline = mock_redis.redis.pipeline.return_value
        pipeline.set.assert_called_once_with("party:1", expected_data)
        pipeline.hset.assert_called_once()
        pipeline.execute.assert_called_once()
