"""Tests for ClanService leave/kick operations."""

from unittest.mock import MagicMock

import pytest

from src.models.clan import Clan, ClanMember, ClanRank
from src.repositories.clan_repository import ClanRepository
from src.services.clan_service import ClanService


class _DummyMapManager:
    def get_player_message_sender(self, _user_id: int):
        return None


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
