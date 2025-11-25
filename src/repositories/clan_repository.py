"""Repository for Clan System persistence in Redis.

Handles storage and retrieval of clans, memberships, and invitations.
"""

# mypy: disable-error-code="misc,no-any-return"
# Redis operations return Any types which cause mypy warnings

import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.models.clan import Clan, ClanInvitation, ClanMember, ClanRank

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


class ClanRepository:
    """Repository for clan data persistence using Redis."""

    # Redis key patterns
    CLAN_KEY = "clan:{clan_id}"
    CLAN_MEMBERS_KEY = "clan:{clan_id}:members"
    CLAN_INDEX_KEY = "clan:index"  # Set of all clan IDs
    USER_CLAN_KEY = "user:{user_id}:clan"  # Current clan of user
    CLAN_NAME_INDEX_KEY = "clan:name:{name}"  # Map clan name to clan_id
    INVITATIONS_KEY = "clan_invitations:{target_id}"  # Pending invitations for user
    NEXT_CLAN_ID_KEY = "clan:next_id"  # Auto-incrementing clan ID
    ALL_CLANS_KEY = "clans:all"  # Hash of all clans

    # Constants
    INVITATION_TIMEOUT = 60  # seconds
    MAX_CLAN_ID = 999999  # Maximum clan ID before reset

    def __init__(self, redis_client: RedisClient) -> None:
        """Initialize repository with Redis client.

        Args:
            redis_client: Redis client instance
        """
        self.redis = redis_client

    async def initialize(self) -> None:
        """Initialize repository - create next clan ID if not exists."""
        exists = await self.redis.redis.exists(self.NEXT_CLAN_ID_KEY)
        if not exists:
            await self.redis.redis.set(self.NEXT_CLAN_ID_KEY, 1)

    async def get_next_clan_id(self) -> int:
        """Get next available clan ID.

        Returns:
            int: The next clan ID.
        """
        clan_id = cast("int", await self.redis.redis.incr(self.NEXT_CLAN_ID_KEY))
        if clan_id > self.MAX_CLAN_ID:
            # Reset to 1 if we exceed maximum
            await self.redis.redis.set(self.NEXT_CLAN_ID_KEY, 1)
            clan_id = 1
        return clan_id

    async def save_clan(self, clan: Clan) -> None:
        """Save complete clan data to Redis."""
        pipe = self.redis.redis.pipeline()

        # Save clan metadata
        clan_data = {
            "clan_id": clan.clan_id,
            "name": clan.name,
            "description": clan.description,
            "leader_id": clan.leader_id,
            "leader_username": clan.leader_username,
            "created_at": clan.created_at,
            "gold": clan.gold,
            "website": clan.website,
            "news": clan.news,
            "member_count": clan.member_count,
            "alliances": list(clan.alliances),
            "wars": list(clan.wars),
            "peace_treaties": list(clan.peace_treaties),
        }

        # Save to main clan key and hash
        pipe.hset(self.ALL_CLANS_KEY, str(clan.clan_id), json.dumps(clan_data))
        pipe.set(self.CLAN_KEY.format(clan_id=clan.clan_id), json.dumps(clan_data))

        # Save clan name index
        pipe.set(self.CLAN_NAME_INDEX_KEY.format(name=clan.name.lower()), clan.clan_id)

        # Reset members hash before storing current snapshot
        members_key = self.CLAN_MEMBERS_KEY.format(clan_id=clan.clan_id)
        pipe.delete(members_key)

        # Save each member
        for member in clan.members.values():
            member_data = {
                "user_id": member.user_id,
                "username": member.username,
                "level": member.level,
                "rank": member.rank.value,
                "joined_at": member.joined_at,
                "is_online": member.is_online,
                "last_seen": member.last_seen,
                "contribution": member.contribution,
            }
            pipe.hset(members_key, str(member.user_id), json.dumps(member_data))

            # Update user's current clan
            pipe.set(self.USER_CLAN_KEY.format(user_id=member.user_id), clan.clan_id)

        # Add to clan index
        pipe.sadd(self.CLAN_INDEX_KEY, clan.clan_id)

        await pipe.execute()

    async def clear_user_clan(self, user_id: int) -> None:
        """Remove the clan reference for a user.

        Args:
            user_id: ID of the user to clear.
        """
        await self.redis.redis.delete(self.USER_CLAN_KEY.format(user_id=user_id))

    async def get_clan(self, clan_id: int) -> Clan | None:
        """Get clan by ID.

        Args:
            clan_id: ID of the clan.

        Returns:
            Clan if found, None otherwise.
        """
        data_str = await self.redis.redis.get(self.CLAN_KEY.format(clan_id=clan_id))
        if not data_str:
            return None

        data = json.loads(data_str)
        members = await self._get_clan_members(clan_id)

        return ClanRepository._deserialize_clan(data, members)

    async def get_clan_by_name(self, name: str) -> Clan | None:
        """Get clan by name (case-insensitive).

        Args:
            name: Name of the clan.

        Returns:
            Clan if found, None otherwise.
        """
        clan_id = await self.redis.redis.get(self.CLAN_NAME_INDEX_KEY.format(name=name.lower()))
        if not clan_id:
            return None

        return await self.get_clan(int(clan_id))

    async def get_user_clan(self, user_id: int) -> Clan | None:
        """Get clan that user belongs to.

        Args:
            user_id: User ID.

        Returns:
            Clan if user is in a clan, None otherwise.
        """
        clan_id = await self.redis.redis.get(self.USER_CLAN_KEY.format(user_id=user_id))
        if not clan_id:
            return None

        return await self.get_clan(int(clan_id))

    async def delete_clan(self, clan_id: int) -> None:
        """Delete a clan and all its data.

        Args:
            clan_id: ID of the clan to delete.
        """
        clan = await self.get_clan(clan_id)
        if not clan:
            return

        pipe = self.redis.redis.pipeline()

        # Remove clan data
        pipe.delete(self.CLAN_KEY.format(clan_id=clan_id))
        pipe.hdel(self.ALL_CLANS_KEY, str(clan_id))
        pipe.delete(self.CLAN_MEMBERS_KEY.format(clan_id=clan_id))
        pipe.delete(self.CLAN_NAME_INDEX_KEY.format(name=clan.name.lower()))

        # Remove user clan references
        for user_id in clan.members:
            pipe.delete(self.USER_CLAN_KEY.format(user_id=user_id))

        # Remove from index
        pipe.srem(self.CLAN_INDEX_KEY, clan_id)

        await pipe.execute()

    async def save_invitation(self, invitation: ClanInvitation) -> None:
        """Save a clan invitation.

        Args:
            invitation: ClanInvitation to save.
        """
        key = self.INVITATIONS_KEY.format(target_id=invitation.target_id)
        data = {
            "clan_id": invitation.clan_id,
            "clan_name": invitation.clan_name,
            "inviter_id": invitation.inviter_id,
            "inviter_username": invitation.inviter_username,
            "target_id": invitation.target_id,
            "target_username": invitation.target_username,
            "created_at": invitation.created_at,
            "expires_at": invitation.expires_at,
        }
        await self.redis.redis.setex(key, self.INVITATION_TIMEOUT, json.dumps(data))

    async def get_invitation(self, target_id: int) -> ClanInvitation | None:
        """Get pending invitation for a user.

        Args:
            target_id: User ID of the invited player.

        Returns:
            ClanInvitation if found, None otherwise.
        """
        key = self.INVITATIONS_KEY.format(target_id=target_id)
        data_str = await self.redis.redis.get(key)
        if not data_str:
            return None

        data = json.loads(data_str)
        return ClanRepository._deserialize_invitation(data)

    async def delete_invitation(self, target_id: int) -> None:
        """Delete an invitation.

        Args:
            target_id: User ID of the invited player.
        """
        key = self.INVITATIONS_KEY.format(target_id=target_id)
        await self.redis.redis.delete(key)

    async def _get_clan_members(self, clan_id: int) -> dict[int, ClanMember]:
        """Get all members of a clan.

        Args:
            clan_id: ID of the clan.

        Returns:
            Dictionary mapping user_id to ClanMember.
        """
        key = self.CLAN_MEMBERS_KEY.format(clan_id=clan_id)
        members_data = await self.redis.redis.hgetall(key)
        members = {}

        for user_id_str, member_data_str in members_data.items():
            member_data = json.loads(member_data_str)
            member = ClanRepository._deserialize_member(member_data)
            members[int(user_id_str)] = member

        return members

    @staticmethod
    def _deserialize_clan(data: dict[str, Any], members: dict[int, ClanMember]) -> Clan:
        """Deserialize clan data from Redis.

        Args:
            data: Clan metadata dictionary.
            members: Dictionary of clan members.

        Returns:
            Clan object.
        """
        return Clan(
            clan_id=data["clan_id"],
            name=data["name"],
            description=data.get("description", ""),
            leader_id=data["leader_id"],
            leader_username=data.get("leader_username", ""),
            members=members,
            created_at=data.get("created_at", time.time()),
            gold=data.get("gold", 0),
            website=data.get("website", ""),
            news=data.get("news", ""),
            alliances=set(data.get("alliances", [])),
            wars=set(data.get("wars", [])),
            peace_treaties=set(data.get("peace_treaties", [])),
        )

    @staticmethod
    def _deserialize_member(data: dict[str, Any]) -> ClanMember:
        """Deserialize clan member data from Redis.

        Args:
            data: Member data dictionary.

        Returns:
            ClanMember object.
        """
        return ClanMember(
            user_id=data["user_id"],
            username=data["username"],
            level=data["level"],
            rank=ClanRank(data.get("rank", 1)),
            joined_at=data.get("joined_at", time.time()),
            is_online=data.get("is_online", True),
            last_seen=data.get("last_seen", time.time()),
            contribution=data.get("contribution", 0),
        )

    @staticmethod
    def _deserialize_invitation(data: dict[str, Any]) -> ClanInvitation:
        """Deserialize invitation data from Redis.

        Args:
            data: Invitation data dictionary.

        Returns:
            ClanInvitation object.
        """
        return ClanInvitation(
            clan_id=data["clan_id"],
            clan_name=data["clan_name"],
            inviter_id=data["inviter_id"],
            inviter_username=data["inviter_username"],
            target_id=data["target_id"],
            target_username=data["target_username"],
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at", time.time() + ClanRepository.INVITATION_TIMEOUT),
        )
