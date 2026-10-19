"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING

from src.models.party import (
    MIN_LEADERSHIP_SCORE,
    MIN_LEVEL_TO_CREATE,
    Party,
)
from src.services.skill_training import read_rules

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.services.party_service import PartyService


class CreationComponent:
    """Coordina creation sin cambiar la fachada existente."""

    def __init__(self, owner: PartyService) -> None:
        """Conserva el contexto y las dependencias del servicio propietario."""
        self.owner = owner

    async def can_create_party(self, user_id: int) -> tuple[bool, str]:
        """Check if user can create a party.

        Returns:
            Tuple of (can_create, error_message)
        """
        # Get player stats
        stats = await self.owner.player_repo.get_stats(user_id)
        if not stats:
            return False, "Usuario no encontrado"

        logger.debug("Party creation check - user %s stats: %s", user_id, stats)

        # Check if user is already in a party
        existing_party = await self.owner.party_repo.get_user_party(user_id)
        if existing_party:
            return False, "Ya perteneces a una party. Escribe /SALIRPARTY para abandonarla"

        # Check if user is alive
        if not await self.owner.player_repo.is_alive(user_id):
            return False, "¡¡Estás muerto!!"

        # Check minimum level requirement
        level = await self.owner.player_repo.get_level(user_id)
        if level < MIN_LEVEL_TO_CREATE:
            return False, f"Debes ser nivel {MIN_LEVEL_TO_CREATE} o superior para crear una party"

        # Get attributes for charisma check
        # Check leadership skill (carisma * liderazgo >= 100)
        # This is from VB6: Carisma * Liderazgo >= 100
        charisma = await self.owner.player_repo.get_charisma(user_id)

        # Get leadership skill
        skills = await self.owner.player_repo.get_skills(user_id)
        leadership = skills.get("liderazgo", 0) if skills else 0

        # Verify leadership requirement (charisma * leadership >= MIN_LEADERSHIP_SCORE)
        leadership_score = charisma * leadership
        required = int(
            (await read_rules(self.owner.player_repo)).get(
                "leadership_party_score", MIN_LEADERSHIP_SCORE
            )
        )
        if leadership_score < required:
            return (
                False,
                (
                    f"Necesitas Carisma * Liderazgo >= {required} "
                    f"(tienes {charisma} * {leadership} = {leadership_score})"
                ),
            )

        return True, ""

    async def create_party(self, user_id: int, username: str = "") -> tuple[Party | None, str]:
        """Create a new party with user as leader.

        Args:
            user_id: User ID creating the party
            username: Username of the leader (optional, will use "Player{user_id}" if not provided)

        Returns:
            Tuple of (party, error_message)
        """
        can_create, error_msg = await self.owner.can_create_party(user_id)
        if not can_create:
            return None, error_msg

        # Use provided username or generate one
        if not username:
            username = f"Player{user_id}"

        # Get next party ID
        party_id = await self.owner.party_repo.get_next_party_id()

        # Create party
        party = Party(party_id=party_id, leader_id=user_id, leader_username=username)

        # Update leader's level in party
        level = await self.owner.player_repo.get_level(user_id)
        party.update_member_level(user_id, level)

        # Save to repository
        await self.owner.party_repo.save_party(party)

        logger.info("Party %s created by user %s (%s)", party_id, user_id, username)

        return party, "¡Has formado una party!"
