"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING

from src.models.party import (
    MAX_LEVEL_DIFFERENCE,
    Party,
    PartyInvitation,
)

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from src.services.party_service import PartyService


class InvitationsComponent:
    """Coordina invitations sin cambiar la fachada existente."""

    def __init__(self, owner: PartyService) -> None:
        """Conserva el contexto y las dependencias del servicio propietario."""
        self.owner = owner

    async def can_invite_to_party(
        self, inviter_id: int, target_id: int
    ) -> tuple[bool, str, Party | None]:
        """Check if inviter can invite target to their party.

        Returns:
            Tuple of (can_invite, error_message, party)
        """
        # Get inviter's party
        party = await self.owner.party_repo.get_user_party(inviter_id)
        if not party:
            return False, "No eres miembro de ninguna party", None

        # Check if inviter is leader
        if not party.is_leader(inviter_id):
            return False, "Solo el líder de la party puede invitar miembros", party

        # Check if party is full
        if party.is_full:
            return False, "La party está llena", party

        # Check if target is already in a party
        target_party = await self.owner.party_repo.get_user_party(target_id)
        if target_party:
            return False, "El usuario ya pertenece a una party", party

        # Check if target exists and is alive
        if not await self.owner.player_repo.is_alive(target_id):
            return False, "Usuario objetivo no encontrado o está muerto", party

        # Check if target meets level requirements
        target_level = await self.owner.player_repo.get_level(target_id)
        if not party.can_join_by_level(target_level):
            return (
                False,
                f"La diferencia de niveles es muy grande (máximo {MAX_LEVEL_DIFFERENCE} niveles)",
                party,
            )

        # Check distance (leaders must be close to invite)
        # This would require position data - for now we'll skip distance check

        return True, "", party

    async def invite_to_party(self, inviter_id: int, target_username: str) -> str:
        """Invite a user to the inviter's party.

        Returns:
            Result message to send to inviter
        """
        # Find target player by username in online players
        if not self.owner.map_manager:
            return "Sistema de invitaciones no disponible"

        # Search for player in all maps
        target_id: int | None = None
        target_map_id: int | None = None
        target_message_sender: MessageSender | None = None

        # Get all online players for debugging
        online_players = self.owner.map_manager.get_all_online_players()
        all_players = [
            f"{username} (ID:{user_id}, Map:{map_id})"
            for user_id, username, map_id in online_players
        ]

        logger.info(
            "Searching for player '%s' in %s maps",
            target_username,
            len(self.owner.map_manager.get_maps_with_players()),
        )

        # Find target player by username
        target_id = self.owner.map_manager.find_player_by_username(target_username)
        target_map_id = None
        target_message_sender = None

        if target_id:
            # Get target's map and message sender
            for user_id, username, map_id in online_players:
                if user_id == target_id:
                    target_map_id = map_id
                    target_message_sender = self.owner.map_manager.get_player_message_sender(
                        target_id
                    )
                    logger.info(
                        "✓ Found target player: %s (ID: %s) in map %s",
                        username,
                        target_id,
                        target_map_id,
                    )
                    break

        logger.info("Online players: %s", ", ".join(all_players) if all_players else "NONE")

        if not target_id:
            available_list = ", ".join(all_players) if all_players else "Ninguno"
            error_msg = (
                f"Jugador '{target_username}' no encontrado o no está online. "
                f"Jugadores disponibles: {available_list}"
            )
            logger.warning(
                "Player '%s' not found. Available: %s",
                target_username,
                available_list,
            )
            return error_msg

        # Check if can invite
        can_invite, error_msg, party = await self.owner.can_invite_to_party(inviter_id, target_id)
        if not can_invite or not party:
            return error_msg

        # Get inviter username from MapManager (the account username, not character name)
        inviter_username = self.owner.map_manager.get_player_username(inviter_id)
        if not inviter_username:
            inviter_username = f"Player{inviter_id}"

        logger.info("Inviter username: '%s' (ID: %s)", inviter_username, inviter_id)

        # Create invitation
        invitation = PartyInvitation(
            party_id=party.party_id,
            inviter_id=inviter_id,
            inviter_username=inviter_username,
            target_id=target_id,
            target_username=target_username,
        )

        # Save invitation
        await self.owner.party_repo.save_invitation(invitation)

        # Send invitation message to target
        if target_message_sender:
            logger.info("Sending invitation message to %s (ID: %s)", target_username, target_id)
            try:
                await target_message_sender.send_console_msg(
                    f"{inviter_username} te ha invitado a su party. Usa /ACCEPTPARTY para aceptar.",
                    font_color=7,
                )
                logger.info("✓ Invitation message sent successfully to %s", target_username)
            except Exception:
                logger.exception("Failed to send invitation message")
        else:
            logger.warning("Could not find MessageSender for player %s", target_id)

        logger.info(
            "User %s invited %s (ID: %s) to party %s",
            inviter_id,
            target_username,
            target_id,
            party.party_id,
        )

        # Send confirmation to inviter
        return f"Has invitado a {target_username} a tu party"

    async def can_accept_invitation(
        self, user_id: int, party_id: int
    ) -> tuple[bool, str, Party | None]:
        """Check if user can accept party invitation.

        Returns:
            Tuple of (can_accept, error_message, party)
        """
        # Get invitation
        invitation = await self.owner.party_repo.get_invitation(user_id, party_id)
        if not invitation:
            return False, "No tienes una invitación para esa party", None

        # Check if invitation is expired
        if invitation.is_expired:
            await self.owner.party_repo.remove_invitation(user_id, party_id)
            return False, "La invitación ha expirado", None

        # Get party
        party = await self.owner.party_repo.get_party(party_id)
        if not party:
            await self.owner.party_repo.remove_invitation(user_id, party_id)
            return False, "La party ya no existe", None
        if party.leader_id != invitation.inviter_id:
            await self.owner.party_repo.remove_invitation(user_id, party_id)
            return False, "La invitación perdió vigencia al cambiar el líder", None

        # Check if party is full
        if party.is_full:
            await self.owner.party_repo.remove_invitation(user_id, party_id)
            return False, "La party está llena", None

        # Check if user is already in a party
        user_party = await self.owner.party_repo.get_user_party(user_id)
        if user_party:
            await self.owner.party_repo.remove_invitation(user_id, party_id)
            return False, "Ya perteneces a una party", None

        # Check if user is dead
        if not await self.owner.player_repo.is_alive(user_id):
            return False, "¡¡Estás muerto!!", party

        return True, "", party

    async def accept_invitation(self, user_id: int, party_id: int) -> str:
        """Accept a party invitation.

        Returns:
            Result message to send to user
        """
        can_accept, error_msg, party = await self.owner.can_accept_invitation(user_id, party_id)
        if not can_accept:
            return error_msg

        # Get player attributes for username
        player_attrs = await self.owner.player_repo.get_attributes(user_id)
        if not player_attrs:
            return "Usuario no encontrado"

        # Get username and level
        username = player_attrs.get("username", f"Player{user_id}")
        if self.owner.map_manager:
            connected_name = self.owner.map_manager.get_player_username(user_id)
            if isinstance(connected_name, str) and connected_name:
                username = connected_name
        level = await self.owner.player_repo.get_level(user_id)

        # Add member to party
        success = party.add_member(user_id, username, level)  # type: ignore[union-attr,arg-type]
        if not success:
            return "No puedes unirte a la party"

        # Save updated party
        await self.owner.party_repo.save_party(party)  # type: ignore[arg-type]

        # Remove invitation
        await self.owner.party_repo.remove_invitation(user_id, party_id)

        # Send messages to all party members
        if self.owner.map_manager:
            for member_id in party.member_ids:  # type: ignore[union-attr]
                # Get member's MessageSender from MapManager
                member_sender = self.owner.get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"¡{username} se ha unido a la party!",
                        font_color=7,  # FONTTYPE_PARTY
                    )

        logger.info("User %s (%s) joined party %s", user_id, username, party_id)

        return f"¡Te has unido a la party de {party.leader_username}!"  # type: ignore[union-attr]

    async def get_user_invitations(self, user_id: int) -> list[PartyInvitation]:
        """Get all pending invitations for user.

        Returns:
            List of pending party invitations.
        """
        return await self.owner.party_repo.get_user_invitations(user_id)
