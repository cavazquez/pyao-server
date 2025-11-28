"""Tests for ClanService operations."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.clan import MIN_LEVEL_TO_CREATE, Clan, ClanMember, ClanRank
from src.repositories.clan_repository import ClanRepository
from src.services.clan_service import ClanService


class _DummyMapManager:
    """Dummy MapManager for testing."""

    def get_player_message_sender(self, _user_id: int):
        return None

    def find_player_by_username(self, username: str) -> int | None:
        """Find player by username for testing."""
        # Mock: return user_id based on username
        username_map = {"Member": 2, "Target": 3, "Officer": 4, "ViceLeader": 5}
        return username_map.get(username)


@pytest.mark.asyncio
async def test_leave_clan_clears_redis_entries(redis_client):
    """Ensure leaving a clan removes membership data from Redis."""
    clan_repo = ClanRepository(redis_client)
    await clan_repo.initialize()

    clan = Clan(clan_id=1, name="TestClan", leader_id=1, leader_username="Leader")
    clan.members[1].level = 20  # type: ignore[index]
    clan.add_member(ClanMember(user_id=2, username="Member", level=15, rank=ClanRank.MEMBER))

    await clan_repo.save_clan(clan)

    clan_service = ClanService(
        clan_repository=clan_repo,
        player_repository=MagicMock(),
        message_sender=MagicMock(),
        broadcast_service=None,
        map_manager=_DummyMapManager(),
    )

    success, _ = await clan_service.leave_clan(user_id=2)
    assert success

    assert await redis_client.redis.get("user:2:clan") is None
    assert await redis_client.redis.hget("clan:1:members", "2") is None


@pytest.mark.asyncio
async def test_kick_member_clears_redis_entries(redis_client):
    """Ensure kicking a clan member removes their data from Redis."""
    clan_repo = ClanRepository(redis_client)
    await clan_repo.initialize()

    clan = Clan(clan_id=2, name="KickClan", leader_id=1, leader_username="Leader")
    clan.members[1].level = 25  # type: ignore[index]
    clan.add_member(ClanMember(user_id=3, username="Target", level=18, rank=ClanRank.MEMBER))

    await clan_repo.save_clan(clan)

    clan_service = ClanService(
        clan_repository=clan_repo,
        player_repository=MagicMock(),
        message_sender=MagicMock(),
        broadcast_service=None,
        map_manager=_DummyMapManager(),
    )

    success, _ = await clan_service.kick_member(kicker_id=1, target_username="Target")
    assert success

    assert await redis_client.redis.get("user:3:clan") is None
    assert await redis_client.redis.hget("clan:2:members", "3") is None


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Create a mock PlayerRepository."""
    repo = MagicMock()
    repo.get_level = AsyncMock(return_value=20)
    repo.get_stats = AsyncMock(return_value={"level": 20})
    repo.is_alive = AsyncMock(return_value=True)
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    return repo


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Create a mock MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    return sender


@pytest.fixture
def clan_service(redis_client, mock_player_repo, mock_message_sender) -> ClanService:
    """Create a ClanService with mocked dependencies."""
    clan_repo = ClanRepository(redis_client)
    return ClanService(
        clan_repository=clan_repo,
        player_repository=mock_player_repo,
        message_sender=mock_message_sender,
        broadcast_service=None,
        map_manager=_DummyMapManager(),
    )


@pytest.mark.asyncio
async def test_create_clan_success(clan_service: ClanService):
    """Test successful clan creation."""
    await clan_service.clan_repo.initialize()

    clan, message = await clan_service.create_clan(
        user_id=1, clan_name="TestClan", description="Test description", username="Leader"
    )

    assert clan is not None
    assert clan.name == "TestClan"
    assert clan.leader_id == 1
    assert "creado" in message.lower()

    # Verify clan is saved in Redis
    saved_clan = await clan_service.clan_repo.get_clan(clan.clan_id)
    assert saved_clan is not None
    assert saved_clan.name == "TestClan"


@pytest.mark.asyncio
async def test_create_clan_duplicate_name(clan_service: ClanService):
    """Test that duplicate clan names are rejected."""
    await clan_service.clan_repo.initialize()

    # Create first clan
    await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader1")

    # Try to create another with same name
    clan, message = await clan_service.create_clan(
        user_id=2, clan_name="TestClan", username="Leader2"
    )

    assert clan is None
    assert "ya existe" in message.lower()


@pytest.mark.asyncio
async def test_create_clan_insufficient_level(clan_service: ClanService):
    """Test that users below minimum level cannot create clans."""
    await clan_service.clan_repo.initialize()

    # Mock low level
    clan_service.player_repo.get_level = AsyncMock(return_value=MIN_LEVEL_TO_CREATE - 1)

    can_create, error_msg = await clan_service.can_create_clan(user_id=1, clan_name="TestClan")

    assert not can_create
    assert "nivel" in error_msg.lower()


@pytest.mark.asyncio
async def test_invite_to_clan_success(clan_service: ClanService):
    """Test successful clan invitation."""
    await clan_service.clan_repo.initialize()

    # Create clan
    clan, _ = await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader")
    assert clan is not None

    # Invite member
    message = await clan_service.invite_to_clan(inviter_id=1, target_username="Member")

    assert "invitado" in message.lower()

    # Verify invitation exists
    invitation = await clan_service.clan_repo.get_invitation(2)  # Member user_id
    assert invitation is not None
    assert invitation.clan_id == clan.clan_id


@pytest.mark.asyncio
async def test_accept_invitation_success(clan_service: ClanService):
    """Test successful invitation acceptance."""
    await clan_service.clan_repo.initialize()

    # Create clan and invite
    clan, _ = await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader")
    await clan_service.invite_to_clan(inviter_id=1, target_username="Member")

    # Accept invitation
    accepted_clan, message = await clan_service.accept_invitation(user_id=2)

    assert accepted_clan is not None
    assert accepted_clan.clan_id == clan.clan_id
    assert "unido" in message.lower()

    # Verify member is in clan
    member = accepted_clan.get_member(2)
    assert member is not None
    assert member.rank == ClanRank.MEMBER


@pytest.mark.asyncio
async def test_reject_invitation_success(clan_service: ClanService):
    """Test successful invitation rejection."""
    await clan_service.clan_repo.initialize()

    # Create clan and invite
    await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader")
    await clan_service.invite_to_clan(inviter_id=1, target_username="Member")

    # Reject invitation
    message = await clan_service.reject_invitation(user_id=2)

    assert "rechazado" in message.lower()

    # Verify invitation is deleted
    invitation = await clan_service.clan_repo.get_invitation(2)
    assert invitation is None


@pytest.mark.asyncio
async def test_promote_member_success(clan_service: ClanService):
    """Test successful member promotion."""
    await clan_service.clan_repo.initialize()

    # Create clan with members
    clan, _ = await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader")
    clan.add_member(ClanMember(user_id=2, username="Member", level=15, rank=ClanRank.MEMBER))
    clan.add_member(
        ClanMember(user_id=4, username="ViceLeader", level=20, rank=ClanRank.VICE_LEADER)
    )
    await clan_service.clan_repo.save_clan(clan)

    # Promote member (by vice leader)
    success, message = await clan_service.promote_member(promoter_id=4, target_username="Member")

    assert success
    assert "promovido" in message.lower()

    # Verify rank was updated
    updated_clan = await clan_service.clan_repo.get_clan(clan.clan_id)
    assert updated_clan is not None
    member = updated_clan.get_member(2)
    assert member is not None
    assert member.rank == ClanRank.OFFICER


@pytest.mark.asyncio
async def test_demote_member_success(clan_service: ClanService):
    """Test successful member demotion."""
    await clan_service.clan_repo.initialize()

    # Create clan with officer
    clan, _ = await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader")
    clan.add_member(ClanMember(user_id=2, username="Officer", level=15, rank=ClanRank.OFFICER))
    clan.add_member(
        ClanMember(user_id=4, username="ViceLeader", level=20, rank=ClanRank.VICE_LEADER)
    )
    await clan_service.clan_repo.save_clan(clan)

    # Demote officer (by vice leader)
    success, message = await clan_service.demote_member(demoter_id=4, target_username="Officer")

    assert success
    assert "degradado" in message.lower()

    # Verify rank was updated
    updated_clan = await clan_service.clan_repo.get_clan(clan.clan_id)
    assert updated_clan is not None
    member = updated_clan.get_member(2)
    assert member is not None
    assert member.rank == ClanRank.MEMBER


@pytest.mark.asyncio
async def test_transfer_leadership_success(clan_service: ClanService):
    """Test successful leadership transfer."""
    await clan_service.clan_repo.initialize()

    # Create clan with member
    clan, _ = await clan_service.create_clan(user_id=1, clan_name="TestClan", username="Leader")
    clan.add_member(ClanMember(user_id=2, username="Member", level=15, rank=ClanRank.MEMBER))
    await clan_service.clan_repo.save_clan(clan)

    # Transfer leadership
    success, message = await clan_service.transfer_leadership(
        leader_id=1, new_leader_username="Member"
    )

    assert success
    assert "transferido" in message.lower()

    # Verify leadership was transferred
    updated_clan = await clan_service.clan_repo.get_clan(clan.clan_id)
    assert updated_clan is not None
    assert updated_clan.leader_id == 2
    assert updated_clan.get_member(2).rank == ClanRank.LEADER
    assert updated_clan.get_member(1).rank == ClanRank.VICE_LEADER
