"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.models.party import (
        Party,
    )
    from src.services.party_service import PartyService


class MembershipComponent:
    """Coordina membership sin cambiar la fachada existente."""

    def __init__(self, owner: PartyService) -> None:
        """Conserva el contexto y las dependencias del servicio propietario."""
        self.owner = owner

    async def leave_party(self, user_id: int) -> str:
        """Leave current party.

        Returns:
            Result message to send to user
        """
        # Get user's party
        party = await self.owner.party_repo.get_user_party(user_id)
        logger.debug("leave_party: user %s party = %s", user_id, party)
        if not party:
            return "No eres miembro de ninguna party"

        # Get username from party member data
        member = party.get_member(user_id)
        username = member.username if member else f"Player{user_id}"

        # Check if user is leader
        if party.is_leader(user_id):
            # If leader leaves, disband party
            # Notify all other members that party was disbanded
            for member_id in party.member_ids:
                if member_id != user_id:
                    member_sender = self.owner.get_player_message_sender(member_id)
                    if member_sender:
                        await member_sender.send_console_msg(
                            f"{username} ha abandonado la party. La party se ha disuelto.",
                            font_color=7,  # FONTTYPE_PARTY
                        )

            await self.owner.party_repo.delete_party(party.party_id)
            logger.info("Party %s disbanded by leader %s", party.party_id, user_id)

            return "Has abandonado la party y se ha disuelto"

        # Regular member leaves
        party.remove_member(user_id)

        # Notify remaining members that someone left
        for member_id in party.member_ids:
            member_sender = self.owner.get_player_message_sender(member_id)
            if member_sender:
                await member_sender.send_console_msg(
                    f"{username} ha abandonado la party.",
                    font_color=7,  # FONTTYPE_PARTY
                )

        # Save updated party
        if party.member_count > 0:
            await self.owner.party_repo.save_party(party)
        else:
            # Disband if empty
            await self.owner.party_repo.delete_party(party.party_id)

        await self.owner.party_repo.remove_member_from_party(party.party_id, user_id)
        logger.info("User %s (%s) left party %s", user_id, username, party.party_id)

        return "Has abandonado la party"

    async def kick_member(self, leader_id: int, target_username: str) -> str:
        """Kick a member from party (leader only).

        Returns:
            Result message to send to leader
        """
        # Get leader's party
        party = await self.owner.party_repo.get_user_party(leader_id)
        if not party:
            return "No eres miembro de ninguna party"

        # Check if user is leader
        if not party.is_leader(leader_id):
            return "Solo el líder puede expulsar miembros"

        # Get target user ID
        target_user_id = self.owner.find_player_by_username(target_username)
        if not target_user_id:
            return f"Usuario '{target_username}' no encontrado o no está online"

        # Check if target is in party
        if not party.is_member(target_user_id):
            return f"{target_username} no es miembro de tu party"

        # Cannot kick yourself
        if target_user_id == leader_id:
            return "No puedes expulsarte a ti mismo. Usa /SALIRPARTY"

        # Remove member
        party.remove_member(target_user_id)

        # Send message to kicked member
        if self.owner.map_manager:
            kicked_sender = self.owner.get_player_message_sender(target_user_id)
            if kicked_sender:
                await kicked_sender.send_console_msg(
                    f"Has sido expulsado de la party por {party.leader_username}.",
                    font_color=7,  # FONTTYPE_PARTY
                )

        # Send messages to remaining members
        if self.owner.map_manager:
            for member_id in party.member_ids:
                member_sender = self.owner.get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{target_username} ha sido expulsado de la party.",
                        font_color=7,  # FONTTYPE_PARTY
                    )

        # Save updated party
        if party.member_count > 0:
            await self.owner.party_repo.save_party(party)
        else:
            # Disband if empty
            await self.owner.party_repo.delete_party(party.party_id)

        await self.owner.party_repo.remove_member_from_party(party.party_id, target_user_id)
        logger.info(
            "User %s (%s) kicked from party %s", target_user_id, target_username, party.party_id
        )

        return f"Has expulsado a {target_username} de la party"

    async def transfer_leadership(self, leader_id: int, target_username: str) -> str:
        """Transfer party leadership to another member.

        Returns:
            Result message to send to leader
        """
        # Get leader's party
        party = await self.owner.party_repo.get_user_party(leader_id)
        if not party:
            return "No eres miembro de ninguna party"

        # Check if user is leader
        if not party.is_leader(leader_id):
            return "Solo el líder puede transferir el liderazgo"

        # Get target user ID
        target_user_id = self.owner.find_player_by_username(target_username)
        if not target_user_id:
            return f"Usuario '{target_username}' no encontrado o no está online"

        # Check if target is in party
        if not party.is_member(target_user_id):
            return f"{target_username} no es miembro de tu party"

        # Transfer leadership
        old_leader_username = party.leader_username
        party.transfer_leadership(target_user_id)

        # Save updated party
        await self.owner.party_repo.save_party(party)

        # Send messages to all members
        if self.owner.map_manager:
            for member_id in party.member_ids:
                member_sender = self.owner.get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"¡{target_username} es el nuevo líder de la party!",
                        font_color=7,  # FONTTYPE_PARTY
                    )

        logger.info(
            "Leadership of party %s transferred from %s to %s",
            party.party_id,
            old_leader_username,
            target_username,
        )

        return f"Has transferido el liderazgo a {target_username}"

    async def get_party_info(self, user_id: int) -> Party | None:
        """Get party information for user.

        Returns:
            Party object if user is in party, None otherwise
        """
        return await self.owner.party_repo.get_user_party(user_id)
