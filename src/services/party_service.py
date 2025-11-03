"""Party Service - Business logic for party system.

Based on AO VB6 server implementation (mdParty.bas)
"""

import logging
from typing import TYPE_CHECKING, Any

from src.models.party import (
    MAX_LEVEL_DIFFERENCE,
    MIN_LEVEL_TO_CREATE,
    Party,
    PartyInvitation,
)

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.broadcast_service import BroadcastService
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.party_repository import PartyRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class PartyService:
    """Service for managing party operations."""

    def __init__(
        self,
        party_repository: PartyRepository,
        player_repository: PlayerRepository,
        message_sender: MessageSender,
        broadcast_service: BroadcastService | None = None,
        map_manager: MapManager | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Initialize party service with dependencies."""
        self.party_repo = party_repository
        self.player_repo = player_repository
        self.message_sender = message_sender
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager
        self.account_repo = account_repo

    def _get_player_message_sender(self, user_id: int) -> MessageSender | None:
        """Get MessageSender for a specific player from MapManager.

        Returns:
            MessageSender if player found, None otherwise.
        """
        if not self.map_manager:
            return None
        return self.map_manager.get_player_message_sender(user_id)

    def _find_player_by_username(self, username: str) -> int | None:
        """Find player user_id by username from MapManager.

        Args:
            username: Username to search for

        Returns:
            user_id if found, None otherwise
        """
        if not self.map_manager:
            logger.warning("MapManager not available for username search")
            return None

        user_id = self.map_manager.find_player_by_username(username)
        if user_id:
            logger.info("Found player '%s' with user_id=%s", username, user_id)
        else:
            logger.warning("Player '%s' not found in any map", username)
        return user_id

    async def can_create_party(self, user_id: int) -> tuple[bool, str]:
        """Check if user can create a party.

        Returns:
            Tuple of (can_create, error_message)
        """
        # Get player stats
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return False, "Usuario no encontrado"

        logger.debug("Party creation check - user %s stats: %s", user_id, stats)

        # Check if user is already in a party
        existing_party = await self.party_repo.get_user_party(user_id)
        if existing_party:
            return False, "Ya perteneces a una party. Escribe /SALIRPARTY para abandonarla"

        # Check if user is dead
        hp = stats.get("min_hp", 0)  # min_hp is the current HP
        logger.debug("Party creation check - user %s HP: %s", user_id, hp)
        if hp <= 0:
            return False, "¡¡Estás muerto!!"

        # Check minimum level requirement
        level = stats.get("level", 1)
        if level < MIN_LEVEL_TO_CREATE:
            return False, f"Debes ser nivel {MIN_LEVEL_TO_CREATE} o superior para crear una party"

        # Get attributes for charisma check
        attributes = await self.player_repo.get_attributes(user_id)
        if not attributes:
            return False, "Error al obtener atributos del jugador"

        # Check leadership skill (carisma * liderazgo >= 100)
        # This is from VB6: Carisma * Liderazgo >= 100
        # For now, we'll use a simplified check since we don't have skills implemented yet
        attributes.get("charisma", 18)  # Default charisma
        # TODO: Get leadership skill when skill system is implemented
        # TODO: Implement leadership check: charisma * leadership >= 100

        return True, ""

    async def create_party(self, user_id: int, username: str = "") -> tuple[Party | None, str]:
        """Create a new party with user as leader.

        Args:
            user_id: User ID creating the party
            username: Username of the leader (optional, will use "Player{user_id}" if not provided)

        Returns:
            Tuple of (party, error_message)
        """
        can_create, error_msg = await self.can_create_party(user_id)
        if not can_create:
            return None, error_msg

        # Get player stats for level
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return None, "Usuario no encontrado"

        # Use provided username or generate one
        if not username:
            username = f"Player{user_id}"

        # Get next party ID
        party_id = await self.party_repo.get_next_party_id()

        # Create party
        party = Party(party_id=party_id, leader_id=user_id, leader_username=username)

        # Update leader's level in party
        level = stats.get("level", 1)
        party.update_member_level(user_id, level)

        # Save to repository
        await self.party_repo.save_party(party)

        logger.info("Party %s created by user %s (%s)", party_id, user_id, username)

        return party, "¡Has formado una party!"

    async def can_invite_to_party(
        self, inviter_id: int, target_id: int
    ) -> tuple[bool, str, Party | None]:
        """Check if inviter can invite target to their party.

        Returns:
            Tuple of (can_invite, error_message, party)
        """
        # Get inviter's party
        party = await self.party_repo.get_user_party(inviter_id)
        if not party:
            return False, "No eres miembro de ninguna party", None

        # Check if inviter is leader
        if not party.is_leader(inviter_id):
            return False, "Solo el líder de la party puede invitar miembros", party

        # Check if party is full
        if party.is_full:
            return False, "La party está llena", party

        # Check if target is already in a party
        target_party = await self.party_repo.get_user_party(target_id)
        if target_party:
            return False, "El usuario ya pertenece a una party", party

        # Get target player stats
        target_stats = await self.player_repo.get_stats(target_id)
        if not target_stats:
            return False, "Usuario objetivo no encontrado", party

        # Check if target meets level requirements
        target_level = target_stats.get("level", 1)
        if not party.can_join_by_level(target_level):
            return (
                False,
                f"La diferencia de niveles es muy grande (máximo {MAX_LEVEL_DIFFERENCE} niveles)",
                party,
            )

        # Check if target is dead
        target_hp = target_stats.get("min_hp", 0)
        if target_hp <= 0:
            return False, "No puedes invitar a usuarios muertos", party

        # Check distance (leaders must be close to invite)
        # This would require position data - for now we'll skip distance check

        return True, "", party

    async def invite_to_party(self, inviter_id: int, target_username: str) -> str:
        """Invite a user to the inviter's party.

        Returns:
            Result message to send to inviter
        """
        # Find target player by username in online players
        if not self.map_manager:
            return "Sistema de invitaciones no disponible"

        # Search for player in all maps
        target_id: int | None = None
        target_map_id: int | None = None
        target_message_sender: MessageSender | None = None

        # Get all online players for debugging
        online_players = self.map_manager.get_all_online_players()
        all_players = [
            f"{username} (ID:{user_id}, Map:{map_id})"
            for user_id, username, map_id in online_players
        ]

        logger.info(
            "Searching for player '%s' in %s maps",
            target_username,
            len(self.map_manager.get_maps_with_players()),
        )

        # Find target player by username
        target_id = self.map_manager.find_player_by_username(target_username)
        target_map_id = None
        target_message_sender = None

        if target_id:
            # Get target's map and message sender
            for user_id, username, map_id in online_players:
                if user_id == target_id:
                    target_map_id = map_id
                    target_message_sender = self.map_manager.get_player_message_sender(target_id)
                    logger.info(
                        "✓ Found target player: %s (ID: %s) in map %s",
                        username,
                        target_id,
                        target_map_id,
                    )
                    break

        logger.info("Online players: %s", ", ".join(all_players) if all_players else "NONE")

        if not target_id:
            logger.warning(
                "Player '%s' not found. Available: %s",
                target_username,
                ", ".join(all_players) if all_players else "NONE",
            )
            return f"Jugador '{target_username}' no encontrado o no está online"

        # Check if can invite
        can_invite, error_msg, party = await self.can_invite_to_party(inviter_id, target_id)
        if not can_invite or not party:
            return error_msg

        # Get inviter username from MapManager (the account username, not character name)
        inviter_username = self.map_manager.get_player_username(inviter_id)
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
        await self.party_repo.save_invitation(invitation)

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
        invitation = await self.party_repo.get_invitation(user_id, party_id)
        if not invitation:
            return False, "No tienes una invitación para esa party", None

        # Check if invitation is expired
        if invitation.is_expired:
            await self.party_repo.remove_invitation(user_id, party_id)
            return False, "La invitación ha expirado", None

        # Get party
        party = await self.party_repo.get_party(party_id)
        if not party:
            await self.party_repo.remove_invitation(user_id, party_id)
            return False, "La party ya no existe", None

        # Check if party is full
        if party.is_full:
            await self.party_repo.remove_invitation(user_id, party_id)
            return False, "La party está llena", None

        # Check if user is already in a party
        user_party = await self.party_repo.get_user_party(user_id)
        if user_party:
            await self.party_repo.remove_invitation(user_id, party_id)
            return False, "Ya perteneces a una party", None

        # Check if user is dead
        user_stats = await self.player_repo.get_stats(user_id)
        if user_stats:
            user_hp = user_stats.get("min_hp", 0)
            if user_hp <= 0:
                return False, "¡¡Estás muerto!!", party

        return True, "", party

    async def accept_invitation(self, user_id: int, party_id: int) -> str:
        """Accept a party invitation.

        Returns:
            Result message to send to user
        """
        can_accept, error_msg, party = await self.can_accept_invitation(user_id, party_id)
        if not can_accept:
            return error_msg

        # Get player stats
        player_stats = await self.player_repo.get_stats(user_id)
        if not player_stats:
            return "Usuario no encontrado"

        # Get player attributes
        player_attrs = await self.player_repo.get_attributes(user_id)
        if not player_attrs:
            return "Usuario no encontrado"

        # Get username and level
        username = player_attrs.get("username", f"Player{user_id}")
        level = player_stats.get("level", 1)

        # Add member to party
        success = party.add_member(user_id, username, level)  # type: ignore[union-attr,arg-type]
        if not success:
            return "No puedes unirte a la party"

        # Save updated party
        await self.party_repo.save_party(party)  # type: ignore[arg-type]

        # Remove invitation
        await self.party_repo.remove_invitation(user_id, party_id)

        # Send messages to all party members
        if self.map_manager:
            for member_id in party.member_ids:  # type: ignore[union-attr]
                # Get member's MessageSender from MapManager
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"¡{username} se ha unido a la party!",
                        font_color=7,  # FONTTYPE_PARTY
                    )

        logger.info("User %s (%s) joined party %s", user_id, username, party_id)

        return f"¡Te has unido a la party de {party.leader_username}!"  # type: ignore[union-attr]

    async def leave_party(self, user_id: int) -> str:
        """Leave current party.

        Returns:
            Result message to send to user
        """
        # Get user's party
        party = await self.party_repo.get_user_party(user_id)
        logger.debug("leave_party: user %s party = %s", user_id, party)
        if not party:
            return "No eres miembro de ninguna party"

        # Get username from party member data
        member = party.get_member(user_id)
        username = member.username if member else f"Player{user_id}"

        # Check if user is leader
        if party.is_leader(user_id):
            # If leader leaves, disband party
            # TODO: Broadcast to members when we have their MessageSenders
            await self.party_repo.delete_party(party.party_id)
            logger.info("Party %s disbanded by leader %s", party.party_id, user_id)

            return "Has abandonado la party y se ha disuelto"

        # Regular member leaves
        party.remove_member(user_id)

        # TODO: Broadcast to remaining members when we have their MessageSenders

        # Save updated party
        if party.member_count > 0:
            await self.party_repo.save_party(party)
        else:
            # Disband if empty
            await self.party_repo.delete_party(party.party_id)

        await self.party_repo.remove_member_from_party(party.party_id, user_id)
        logger.info("User %s (%s) left party %s", user_id, username, party.party_id)

        return "Has abandonado la party"

    async def kick_member(self, leader_id: int, target_username: str) -> str:
        """Kick a member from party (leader only).

        Returns:
            Result message to send to leader
        """
        # Get leader's party
        party = await self.party_repo.get_user_party(leader_id)
        if not party:
            return "No eres miembro de ninguna party"

        # Check if user is leader
        if not party.is_leader(leader_id):
            return "Solo el líder puede expulsar miembros"

        # Get target user ID
        target_user_id = self._find_player_by_username(target_username)
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
        if self.map_manager:
            kicked_sender = self._get_player_message_sender(target_user_id)
            if kicked_sender:
                await kicked_sender.send_console_msg(
                    f"Has sido expulsado de la party por {party.leader_username}.",
                    font_color=7,  # FONTTYPE_PARTY
                )

        # Send messages to remaining members
        if self.map_manager:
            for member_id in party.member_ids:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{target_username} ha sido expulsado de la party.",
                        font_color=7,  # FONTTYPE_PARTY
                    )

        # Save updated party
        if party.member_count > 0:
            await self.party_repo.save_party(party)
        else:
            # Disband if empty
            await self.party_repo.delete_party(party.party_id)

        await self.party_repo.remove_member_from_party(party.party_id, target_user_id)
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
        party = await self.party_repo.get_user_party(leader_id)
        if not party:
            return "No eres miembro de ninguna party"

        # Check if user is leader
        if not party.is_leader(leader_id):
            return "Solo el líder puede transferir el liderazgo"

        # Get target user ID
        target_user_id = self._find_player_by_username(target_username)
        if not target_user_id:
            return f"Usuario '{target_username}' no encontrado o no está online"

        # Check if target is in party
        if not party.is_member(target_user_id):
            return f"{target_username} no es miembro de tu party"

        # Transfer leadership
        old_leader_username = party.leader_username
        party.transfer_leadership(target_user_id)

        # Save updated party
        await self.party_repo.save_party(party)

        # Send messages to all members
        if self.map_manager:
            for member_id in party.member_ids:
                member_sender = self._get_player_message_sender(member_id)
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

    async def send_party_message(self, sender_id: int, message: str) -> str:
        """Send message to all party members.

        Returns:
            Result message to send to sender
        """
        # Get sender's party
        party = await self.party_repo.get_user_party(sender_id)
        if not party:
            return "No eres miembro de ninguna party"

        # Get sender username from account
        sender_username = f"Usuario#{sender_id}"
        if self.account_repo:
            account_data = await self.account_repo.get_account_by_user_id(sender_id)
            if account_data:
                sender_username = account_data.get("username", sender_username)
        logger.info("Party message from %s (ID:%s): '%s'", sender_username, sender_id, message)

        # Send message to all members
        if self.map_manager:
            for member_id in party.member_ids:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    full_message = f"[Party] {sender_username}: {message}"
                    logger.debug("Sending to member %s: '%s'", member_id, full_message)
                    await member_sender.send_console_msg(
                        full_message,
                        font_color=7,  # FONTTYPE_PARTY (verde para party)
                    )

        return ""

    async def get_party_info(self, user_id: int) -> Party | None:
        """Get party information for user.

        Returns:
            Party object if user is in party, None otherwise
        """
        return await self.party_repo.get_user_party(user_id)

    async def get_user_invitations(self, user_id: int) -> list[PartyInvitation]:
        """Get all pending invitations for user.

        Returns:
            List of pending party invitations.
        """
        return await self.party_repo.get_user_invitations(user_id)

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
        party = await self.party_repo.get_user_party(earner_id)
        if not party:
            return {}

        # Helper functions to get player data
        async def get_user_level(user_id: int) -> int | None:
            stats = await self.player_repo.get_stats(user_id)
            return stats.get("level") if stats else None

        async def get_user_position(user_id: int) -> dict[str, Any] | None:
            position = await self.player_repo.get_position(user_id)
            return position or None

        async def is_user_alive(user_id: int) -> bool:
            stats = await self.player_repo.get_stats(user_id)
            if not stats:
                return False
            return stats.get("min_hp", 0) > 0

        # Distribute experience
        distributed_exp = await party.distribute_experience(
            exp_amount, map_id, x, y, get_user_level, get_user_position, is_user_alive
        )

        # Save updated party data
        await self.party_repo.update_party_metadata(party)

        # Update individual members
        for user_id in distributed_exp:
            member = party.get_member(user_id)
            if member:
                await self.party_repo.update_member(party.party_id, member)

        return distributed_exp

    async def update_member_level(self, user_id: int, new_level: int) -> bool:
        """Update member's level in their party.

        Returns:
            True if updated successfully, False if not in party
        """
        party = await self.party_repo.get_user_party(user_id)
        if not party:
            return False

        success = party.update_member_level(user_id, new_level)
        if success:
            await self.party_repo.update_party_metadata(party)

            # Update member data
            member = party.get_member(user_id)
            if member:
                await self.party_repo.update_member(party.party_id, member)

        return success

    async def set_member_online_status(self, user_id: int, is_online: bool) -> bool:
        """Set online status of party member.

        Returns:
            True if updated successfully, False if not in party
        """
        party = await self.party_repo.get_user_party(user_id)
        if not party:
            return False

        success = party.set_member_online_status(user_id, is_online)
        if success:
            member = party.get_member(user_id)
            if member:
                await self.party_repo.update_member(party.party_id, member)

        return success
