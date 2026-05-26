"""Clan service mixins."""

import logging

from src.models.clan import (
    MAX_CLAN_DESCRIPTION_LENGTH,
    MAX_CLAN_NAME_LENGTH,
    MIN_LEVEL_TO_CREATE,
    Clan,
)
from src.services.clan._base import ClanServiceMixinBase

logger = logging.getLogger(__name__)


class ClanCreationMixin(ClanServiceMixinBase):
    """Create clans and validate creation requirements."""

    async def can_create_clan(self, user_id: int, clan_name: str) -> tuple[bool, str]:
        """Check if user can create a clan.

        Args:
            user_id: User ID attempting to create clan
            clan_name: Name of the clan to create

        Returns:
            Tuple of (can_create, error_message)
        """
        # Validate clan name
        if not clan_name or not clan_name.strip():
            return False, "El nombre del clan no puede estar vacío"

        clan_name = clan_name.strip()

        if len(clan_name) > MAX_CLAN_NAME_LENGTH:
            return (
                False,
                f"El nombre del clan no puede tener más de {MAX_CLAN_NAME_LENGTH} caracteres",
            )

        # Check if clan name already exists
        existing_clan = await self.clan_repo.get_clan_by_name(clan_name)
        if existing_clan:
            return False, f"Ya existe un clan con el nombre '{clan_name}'"

        # Get player stats
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return False, "Usuario no encontrado"

        # Check if user is already in a clan
        existing_clan = await self.clan_repo.get_user_clan(user_id)
        if existing_clan:
            return False, "Ya perteneces a un clan. Escribe /SALIRCLAN para abandonarlo"

        # Check if user is alive
        if not await self.player_repo.is_alive(user_id):
            return False, "¡¡Estás muerto!!"

        # Check minimum level requirement
        level = await self.player_repo.get_level(user_id)
        if level < MIN_LEVEL_TO_CREATE:
            return False, f"Debes ser nivel {MIN_LEVEL_TO_CREATE} o superior para crear un clan"

        return True, ""

    async def create_clan(
        self, user_id: int, clan_name: str, description: str = "", username: str = ""
    ) -> tuple[Clan | None, str]:
        """Create a new clan with user as leader.

        Args:
            user_id: User ID creating the clan
            clan_name: Name of the clan
            description: Optional description of the clan
            username: Username of the leader (optional)

        Returns:
            Tuple of (clan, error_message)
        """
        can_create, error_msg = await self.can_create_clan(user_id, clan_name)
        if not can_create:
            return None, error_msg

        # Validate description length
        if len(description) > MAX_CLAN_DESCRIPTION_LENGTH:
            return (
                None,
                f"La descripción no puede tener más de {MAX_CLAN_DESCRIPTION_LENGTH} caracteres",
            )

        # Use provided username or generate one
        if not username:
            username = f"Player{user_id}"

        # Get player level
        level = await self.player_repo.get_level(user_id)
        if level == 0:  # get_level returns 1 by default, so 0 means user doesn't exist
            return None, "Usuario no encontrado"

        # Get next clan ID
        clan_id = await self.clan_repo.get_next_clan_id()

        # Create clan
        clan = Clan(
            clan_id=clan_id,
            name=clan_name.strip(),
            description=description.strip(),
            leader_id=user_id,
            leader_username=username,
        )

        # Update leader's level
        if user_id in clan.members:
            clan.members[user_id].level = level

        # Save to repository
        await self.clan_repo.save_clan(clan)

        logger.info("Clan %s '%s' created by user %s (%s)", clan_id, clan_name, user_id, username)

        return clan, f"¡Has creado el clan '{clan_name}'!"
