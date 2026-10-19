"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.services.party_service import PartyService


class ExperienceComponent:
    """Coordina experience sin cambiar la fachada existente."""

    def __init__(self, owner: PartyService) -> None:
        """Conserva el contexto y las dependencias del servicio propietario."""
        self.owner = owner

    async def distribute_experience(
        self, earner_id: int, exp_amount: int, map_id: int, x: int, y: int
    ) -> dict[int, float]:
        """Distribute experience to party members within range.

        Args:
            earner_id: ID of the user who earned the experience.
            exp_amount: Amount of experience to distribute.
            map_id: Map ID where experience was earned.
            x: X coordinate where experience was earned.
            y: Y coordinate where experience was earned.

        Returns:
            Dictionary mapping user_id -> experience_amount
        """
        party = await self.owner.party_repo.get_user_party(earner_id)
        if not party:
            return {}

        # Helper functions to get player data
        async def get_user_level(user_id: int) -> int | None:
            return await self.owner.player_repo.get_level(user_id)

        async def get_user_position(user_id: int) -> dict[str, Any] | None:
            position = await self.owner.player_repo.get_position(user_id)
            return position or None

        async def is_user_alive(user_id: int) -> bool:
            return await self.owner.player_repo.is_alive(user_id)

        # Distribute experience
        distributed_exp = await party.distribute_experience(
            exp_amount, map_id, x, y, get_user_level, get_user_position, is_user_alive
        )

        # Save updated party data
        await self.owner.party_repo.update_party_metadata(party)

        # Update individual members
        for user_id in distributed_exp:
            member = party.get_member(user_id)
            if member:
                await self.owner.party_repo.update_member(party.party_id, member)

        return distributed_exp

    async def update_member_level(self, user_id: int, new_level: int) -> bool:
        """Update member's level in their party.

        Returns:
            True if updated successfully, False if not in party
        """
        party = await self.owner.party_repo.get_user_party(user_id)
        if not party:
            return False

        success = party.update_member_level(user_id, new_level)
        if success:
            await self.owner.party_repo.update_party_metadata(party)

            # Update member data
            member = party.get_member(user_id)
            if member:
                await self.owner.party_repo.update_member(party.party_id, member)

        return success

    async def set_member_online_status(self, user_id: int, is_online: bool) -> bool:
        """Set online status of party member.

        Returns:
            True if updated successfully, False if not in party
        """
        party = await self.owner.party_repo.get_user_party(user_id)
        if not party:
            return False

        success = party.set_member_online_status(user_id, is_online)
        if success:
            member = party.get_member(user_id)
            if member:
                await self.owner.party_repo.update_member(party.party_id, member)

        return success
