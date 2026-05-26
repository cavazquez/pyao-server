"""Clan service mixins."""

import logging

from src.models.clan import (
    ClanRank,
)
from src.services.clan._helpers import CLAN_RANK_NAMES, ClanServiceHelpersMixin

logger = logging.getLogger(__name__)


class ClanRankMixin(ClanServiceHelpersMixin):
    """Promote, demote, and transfer clan leadership."""

    async def promote_member(self, promoter_id: int, target_username: str) -> tuple[bool, str]:
        """Promote a member's rank.

        Args:
            promoter_id: User ID of the member doing the promotion
            target_username: Username of the member to promote

        Returns:
            Tuple of (success, message)
        """
        clan = await self.clan_repo.get_user_clan(promoter_id)
        if not clan:
            return False, "No perteneces a ningún clan"

        promoter_member = clan.get_member(promoter_id)
        if not promoter_member or not promoter_member.can_promote_demote():
            return False, "No tienes permiso para promover miembros"

        # Find target member
        target_id = None
        for member_id, member in clan.members.items():
            if member.username.lower() == target_username.lower():
                target_id = member_id
                break

        if not target_id:
            return False, f"'{target_username}' no es miembro del clan"

        target_member = clan.get_member(target_id)
        if not target_member:
            return False, "Error: miembro no encontrado"

        # Cannot promote leader
        if target_member.rank == ClanRank.LEADER:
            return False, "El líder ya tiene el rango máximo"

        # Determine new rank
        new_rank_value = min(target_member.rank.value + 1, ClanRank.VICE_LEADER.value)
        new_rank = ClanRank(new_rank_value)

        # Update rank
        if not clan.update_member_rank(target_id, new_rank):
            return False, "Error al promover miembro"

        # Save clan
        await self.clan_repo.save_clan(clan)

        # Notify the promoted member
        promoted_sender = self._get_player_message_sender(target_id)
        if promoted_sender:
            await promoted_sender.send_console_msg(
                f"Has sido promovido a {CLAN_RANK_NAMES[new_rank]} en el clan '{clan.name}'",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (promovido)", target_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", target_id)

        # Notify the promoter
        promoter_sender = self._get_player_message_sender(promoter_id)
        if promoter_sender:
            await promoter_sender.send_console_msg(
                f"Has promovido a '{target_username}' a {CLAN_RANK_NAMES[new_rank]}",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (promotor)", promoter_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", promoter_id)

        # Notify all other clan members
        for member_id in clan.members:
            if member_id not in {promoter_id, target_id}:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{target_username} ha sido promovido a {CLAN_RANK_NAMES[new_rank]} "
                        f"en el clan '{clan.name}'",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                    logger.debug("Notificación enviada a user_id %s (miembro del clan)", member_id)
                else:
                    logger.debug(
                        "No se pudo enviar notificación a user_id %s (no conectado)", member_id
                    )

        logger.info(
            "User %s promoted %s to %s in clan %s",
            promoter_id,
            target_username,
            new_rank,
            clan.name,
        )

        return True, f"Has promovido a '{target_username}' a {CLAN_RANK_NAMES[new_rank]}"

    async def demote_member(self, demoter_id: int, target_username: str) -> tuple[bool, str]:
        """Demote a member's rank.

        Args:
            demoter_id: User ID of the member doing the demotion
            target_username: Username of the member to demote

        Returns:
            Tuple of (success, message)
        """
        clan = await self.clan_repo.get_user_clan(demoter_id)
        if not clan:
            return False, "No perteneces a ningún clan"

        demoter_member = clan.get_member(demoter_id)
        if not demoter_member or not demoter_member.can_promote_demote():
            return False, "No tienes permiso para degradar miembros"

        # Find target member
        target_id = None
        for member_id, member in clan.members.items():
            if member.username.lower() == target_username.lower():
                target_id = member_id
                break

        if not target_id:
            return False, f"'{target_username}' no es miembro del clan"

        target_member = clan.get_member(target_id)
        if not target_member:
            return False, "Error: miembro no encontrado"

        # Cannot demote leader
        if target_member.rank == ClanRank.LEADER:
            return False, "No puedes degradar al líder del clan"

        # Determine new rank
        new_rank_value = max(target_member.rank.value - 1, ClanRank.MEMBER.value)
        new_rank = ClanRank(new_rank_value)

        # Update rank
        if not clan.update_member_rank(target_id, new_rank):
            return False, "Error al degradar miembro"

        # Save clan
        await self.clan_repo.save_clan(clan)

        # Notify the demoted member
        demoted_sender = self._get_player_message_sender(target_id)
        if demoted_sender:
            await demoted_sender.send_console_msg(
                f"Has sido degradado a {CLAN_RANK_NAMES[new_rank]} en el clan '{clan.name}'",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (degradado)", target_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", target_id)

        # Notify the demoter
        demoter_sender = self._get_player_message_sender(demoter_id)
        if demoter_sender:
            await demoter_sender.send_console_msg(
                f"Has degradado a '{target_username}' a {CLAN_RANK_NAMES[new_rank]}",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (degradador)", demoter_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", demoter_id)

        # Notify all other clan members
        for member_id in clan.members:
            if member_id not in {demoter_id, target_id}:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{target_username} ha sido degradado a {CLAN_RANK_NAMES[new_rank]} "
                        f"en el clan '{clan.name}'",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                    logger.debug("Notificación enviada a user_id %s (miembro del clan)", member_id)
                else:
                    logger.debug(
                        "No se pudo enviar notificación a user_id %s (no conectado)", member_id
                    )

        logger.info(
            "User %s demoted %s to %s in clan %s", demoter_id, target_username, new_rank, clan.name
        )

        return True, f"Has degradado a '{target_username}' a {CLAN_RANK_NAMES[new_rank]}"

    async def transfer_leadership(
        self, leader_id: int, new_leader_username: str
    ) -> tuple[bool, str]:
        """Transfer clan leadership to another member.

        Args:
            leader_id: User ID of the current leader
            new_leader_username: Username of the new leader

        Returns:
            Tuple of (success, message)
        """
        clan = await self.clan_repo.get_user_clan(leader_id)
        if not clan:
            return False, "No perteneces a ningún clan"

        leader_member = clan.get_member(leader_id)
        if not leader_member or leader_member.rank != ClanRank.LEADER:
            return False, "Solo el líder puede transferir el liderazgo"

        # Find new leader
        new_leader_id = None
        for member_id, member in clan.members.items():
            if member.username.lower() == new_leader_username.lower():
                new_leader_id = member_id
                break

        if not new_leader_id:
            return False, f"'{new_leader_username}' no es miembro del clan"

        if new_leader_id == leader_id:
            return False, "Ya eres el líder del clan"

        # Get old and new leader usernames before transfer
        old_leader_username = leader_member.username
        new_leader_member = clan.get_member(new_leader_id)
        new_leader_username = (
            new_leader_member.username if new_leader_member else new_leader_username
        )

        # Transfer leadership
        if not clan.transfer_leadership(new_leader_id):
            return False, "Error al transferir el liderazgo"

        # Save clan
        await self.clan_repo.save_clan(clan)

        # Notify the old leader
        old_leader_sender = self._get_player_message_sender(leader_id)
        if old_leader_sender:
            await old_leader_sender.send_console_msg(
                f"Has transferido el liderazgo del clan '{clan.name}' a '{new_leader_username}'",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (líder anterior)", leader_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", leader_id)

        # Notify the new leader
        new_leader_sender = self._get_player_message_sender(new_leader_id)
        if new_leader_sender:
            await new_leader_sender.send_console_msg(
                f"¡Has sido nombrado líder del clan '{clan.name}'!",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (nuevo líder)", new_leader_id)
        else:
            logger.debug(
                "No se pudo enviar notificación a user_id %s (no conectado)", new_leader_id
            )

        # Notify all other clan members
        for member_id in clan.members:
            if member_id not in {leader_id, new_leader_id}:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{old_leader_username} ha transferido el liderazgo del clan "
                        f"'{clan.name}' a {new_leader_username}",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                    logger.debug("Notificación enviada a user_id %s (miembro del clan)", member_id)
                else:
                    logger.debug(
                        "No se pudo enviar notificación a user_id %s (no conectado)", member_id
                    )

        logger.info(
            "Leadership of clan %s transferred from %s to %s", clan.name, leader_id, new_leader_id
        )

        return True, f"Has transferido el liderazgo del clan a '{new_leader_username}'"
