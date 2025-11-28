"""Clan Service - Business logic for clan/guild system.

Based on AO VB6 server implementation (modGuilds.bas)
"""

import logging
from typing import TYPE_CHECKING

from src.models.clan import (
    MAX_CLAN_DESCRIPTION_LENGTH,
    MAX_CLAN_NAME_LENGTH,
    MIN_LEVEL_TO_CREATE,
    MIN_LEVEL_TO_JOIN,
    Clan,
    ClanInvitation,
    ClanMember,
    ClanRank,
)

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.broadcast_service import BroadcastService
    from src.messaging.message_sender import MessageSender
    from src.repositories.clan_repository import ClanRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class ClanService:
    """Service for managing clan operations."""

    def __init__(
        self,
        clan_repository: ClanRepository,
        player_repository: PlayerRepository,
        message_sender: MessageSender,
        broadcast_service: BroadcastService | None = None,
        map_manager: MapManager | None = None,
    ) -> None:
        """Initialize clan service with dependencies."""
        self.clan_repo = clan_repository
        self.player_repo = player_repository
        self.message_sender = message_sender
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager

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

    async def can_invite_to_clan(
        self, inviter_id: int, target_id: int
    ) -> tuple[bool, str, Clan | None]:
        """Check if inviter can invite target to their clan.

        Args:
            inviter_id: User ID of the inviter
            target_id: User ID of the target

        Returns:
            Tuple of (can_invite, error_message, clan)
        """
        # Get inviter's clan
        clan = await self.clan_repo.get_user_clan(inviter_id)
        if not clan:
            return False, "No eres miembro de ningún clan", None

        # Check if inviter has permission to invite
        inviter_member = clan.get_member(inviter_id)
        if not inviter_member or not inviter_member.can_invite_members():
            return False, "No tienes permiso para invitar miembros al clan", clan

        # Check if clan is full
        if clan.is_full:
            return False, "El clan está lleno", clan

        # Check if target is already in a clan
        target_clan = await self.clan_repo.get_user_clan(target_id)
        if target_clan:
            return False, "El usuario ya pertenece a un clan", clan

        # Check if target exists and is alive
        if not await self.player_repo.is_alive(target_id):
            return False, "Usuario objetivo no encontrado o está muerto", clan

        # Check minimum level requirement
        target_level = await self.player_repo.get_level(target_id)
        if target_level < MIN_LEVEL_TO_JOIN:
            return False, f"El usuario debe ser nivel {MIN_LEVEL_TO_JOIN} o superior", clan

        return True, "", clan

    async def invite_to_clan(self, inviter_id: int, target_username: str) -> str:
        """Invite a user to the inviter's clan.

        Args:
            inviter_id: User ID of the inviter
            target_username: Username of the target

        Returns:
            Success or error message
        """
        # Find target user
        target_id = self._find_player_by_username(target_username)
        if not target_id:
            return f"Usuario '{target_username}' no encontrado"

        # Check if can invite
        can_invite, error_msg, clan = await self.can_invite_to_clan(inviter_id, target_id)
        if not can_invite or not clan:
            return error_msg

        # Get inviter and target usernames
        inviter_member = clan.get_member(inviter_id)
        if not inviter_member:
            return "Error: no se encontró tu información en el clan"

        # Check if invitation already exists
        existing_invitation = await self.clan_repo.get_invitation(target_id)
        if existing_invitation:
            if existing_invitation.clan_id == clan.clan_id:
                return f"Ya hay una invitación pendiente para '{target_username}'"
            # Delete old invitation
            await self.clan_repo.delete_invitation(target_id)

        # Create invitation
        invitation = ClanInvitation(
            clan_id=clan.clan_id,
            clan_name=clan.name,
            inviter_id=inviter_id,
            inviter_username=inviter_member.username,
            target_id=target_id,
            target_username=target_username,
        )

        # Save invitation
        await self.clan_repo.save_invitation(invitation)

        # Notify target
        target_sender = self._get_player_message_sender(target_id)
        if target_sender:
            await target_sender.send_console_msg(
                f"{inviter_member.username} te ha invitado a unirte al clan '{clan.name}'. "
                f"Escribe /ACEPTARCLAN para aceptar o /RECHAZARCLAN para rechazar."
            )

        logger.info(
            "Clan invitation: %s invited %s to clan %s",
            inviter_member.username,
            target_username,
            clan.name,
        )

        return f"Has invitado a '{target_username}' a unirse al clan '{clan.name}'"

    async def accept_invitation(self, user_id: int) -> tuple[Clan | None, str]:
        """Accept a pending clan invitation.

        Args:
            user_id: User ID accepting the invitation

        Returns:
            Tuple of (clan, error_message)
        """
        # Get pending invitation
        invitation = await self.clan_repo.get_invitation(user_id)
        if not invitation:
            return None, "No tienes invitaciones pendientes"

        if invitation.is_expired():
            await self.clan_repo.delete_invitation(user_id)
            return None, "La invitación ha expirado"

        # Get clan
        clan = await self.clan_repo.get_clan(invitation.clan_id)
        if not clan:
            await self.clan_repo.delete_invitation(user_id)
            return None, "El clan ya no existe"

        # Check if clan is still not full
        if clan.is_full:
            await self.clan_repo.delete_invitation(user_id)
            return None, "El clan está lleno"

        # Get player level
        level = await self.player_repo.get_level(user_id)
        if level == 0:  # get_level returns 1 by default, so 0 means user doesn't exist
            return None, "Usuario no encontrado"

        # Create member
        member = ClanMember(
            user_id=user_id,
            username=invitation.target_username,
            level=level,
            rank=ClanRank.MEMBER,
        )

        # Add member to clan
        if not clan.add_member(member):
            return None, "Error al agregar miembro al clan"

        # Save clan
        await self.clan_repo.save_clan(clan)

        # Delete invitation
        await self.clan_repo.delete_invitation(user_id)

        logger.info("User %s joined clan %s", user_id, clan.name)

        return clan, f"Te has unido al clan '{clan.name}'"

    async def reject_invitation(self, user_id: int) -> str:
        """Reject a pending clan invitation.

        Args:
            user_id: User ID rejecting the invitation

        Returns:
            Success or error message
        """
        invitation = await self.clan_repo.get_invitation(user_id)
        if not invitation:
            return "No tienes invitaciones pendientes"

        await self.clan_repo.delete_invitation(user_id)
        return f"Has rechazado la invitación al clan '{invitation.clan_name}'"

    async def leave_clan(self, user_id: int) -> tuple[bool, str]:
        """Leave the current clan.

        Args:
            user_id: User ID leaving the clan

        Returns:
            Tuple of (success, message)
        """
        clan = await self.clan_repo.get_user_clan(user_id)
        if not clan:
            return False, "No perteneces a ningún clan"

        member = clan.get_member(user_id)
        if not member:
            return False, "Error: no se encontró tu información en el clan"

        # Cannot leave if you're the leader (must transfer leadership first)
        if member.rank == ClanRank.LEADER:
            return (
                False,
                "No puedes abandonar el clan siendo el líder. Transfiere el liderazgo primero.",
            )

        # Get member info before removal
        member_username = member.username

        # Remove member
        if not clan.remove_member(user_id):
            return False, "Error al remover miembro del clan"

        # Save clan
        await self.clan_repo.save_clan(clan)

        # Notify the player who left
        leaving_sender = self._get_player_message_sender(user_id)
        if leaving_sender:
            await leaving_sender.send_console_msg(
                f"Has abandonado el clan '{clan.name}'",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (abandonó clan)", user_id)
        else:
            logger.warning("No se pudo enviar notificación a user_id %s (no conectado)", user_id)

        # Notify remaining clan members
        for member_id in clan.members:
            if member_id != user_id:  # Don't notify the one who left
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{member_username} ha abandonado el clan '{clan.name}'",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                    logger.debug("Notificación enviada a user_id %s (miembro restante)", member_id)
                else:
                    logger.debug(
                        "No se pudo enviar notificación a user_id %s (no conectado)", member_id
                    )

        # Clear membership reference in Redis
        await self.clan_repo.clear_user_clan(user_id)

        logger.info("User %s left clan %s", user_id, clan.name)

        return True, f"Has abandonado el clan '{clan.name}'"

    async def kick_member(self, kicker_id: int, target_username: str) -> tuple[bool, str]:
        """Kick a member from the clan.

        Args:
            kicker_id: User ID of the member doing the kick
            target_username: Username of the member to kick

        Returns:
            Tuple of (success, message)
        """
        clan = await self.clan_repo.get_user_clan(kicker_id)
        if not clan:
            return False, "No perteneces a ningún clan"

        kicker_member = clan.get_member(kicker_id)
        if not kicker_member or not kicker_member.can_kick_members():
            return False, "No tienes permiso para expulsar miembros"

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

        # Cannot kick leader
        if target_member.rank == ClanRank.LEADER:
            return False, "No puedes expulsar al líder del clan"

        # Cannot kick yourself
        if target_id == kicker_id:
            return False, "No puedes expulsarte a ti mismo"

        # Get target member info before removal
        target_member_username = target_member.username

        # Remove member
        if not clan.remove_member(target_id):
            return False, "Error al expulsar miembro"

        # Save clan
        await self.clan_repo.save_clan(clan)

        # Notify the kicked player
        kicked_sender = self._get_player_message_sender(target_id)
        if kicked_sender:
            await kicked_sender.send_console_msg(
                f"Has sido expulsado del clan '{clan.name}'",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            logger.debug("Notificación enviada a user_id %s (expulsado)", target_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", target_id)

        # Notify the kicker
        kicker_sender = self._get_player_message_sender(kicker_id)
        if kicker_sender:
            await kicker_sender.send_console_msg(
                f"Has expulsado a '{target_username}' del clan '{clan.name}'",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (expulsador)", kicker_id)
        else:
            logger.warning("No se pudo enviar notificación a user_id %s (no conectado)", kicker_id)

        # Notify remaining clan members
        for member_id in clan.members:
            if member_id not in {kicker_id, target_id}:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{target_member_username} ha sido expulsado del clan '{clan.name}'",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                    logger.debug("Notificación enviada a user_id %s (miembro restante)", member_id)
                else:
                    logger.debug(
                        "No se pudo enviar notificación a user_id %s (no conectado)", member_id
                    )

        # Clear membership reference in Redis
        await self.clan_repo.clear_user_clan(target_id)

        logger.info("User %s kicked %s from clan %s", kicker_id, target_username, clan.name)

        return True, f"Has expulsado a '{target_username}' del clan"

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

        rank_names = {
            ClanRank.MEMBER: "Miembro",
            ClanRank.OFFICER: "Oficial",
            ClanRank.VICE_LEADER: "Vice Líder",
            ClanRank.LEADER: "Líder",
        }

        logger.info(
            "User %s promoted %s to %s in clan %s",
            promoter_id,
            target_username,
            new_rank,
            clan.name,
        )

        return True, f"Has promovido a '{target_username}' a {rank_names[new_rank]}"

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

        rank_names = {
            ClanRank.MEMBER: "Miembro",
            ClanRank.OFFICER: "Oficial",
            ClanRank.VICE_LEADER: "Vice Líder",
            ClanRank.LEADER: "Líder",
        }

        logger.info(
            "User %s demoted %s to %s in clan %s", demoter_id, target_username, new_rank, clan.name
        )

        return True, f"Has degradado a '{target_username}' a {rank_names[new_rank]}"

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

        # Transfer leadership
        if not clan.transfer_leadership(new_leader_id):
            return False, "Error al transferir el liderazgo"

        # Save clan
        await self.clan_repo.save_clan(clan)

        logger.info(
            "Leadership of clan %s transferred from %s to %s", clan.name, leader_id, new_leader_id
        )

        return True, f"Has transferido el liderazgo del clan a '{new_leader_username}'"

    async def send_clan_message(self, sender_id: int, message: str) -> str:
        """Send message to all clan members.

        Args:
            sender_id: User ID of the message sender.
            message: Message content.

        Returns:
            Error message if failed, empty string if successful.
        """
        # Get sender's clan
        clan = await self.clan_repo.get_user_clan(sender_id)
        if not clan:
            return "No perteneces a ningún clan"

        # Get sender member info
        sender_member = clan.get_member(sender_id)
        if not sender_member:
            return "Error: no se encontró tu información en el clan"

        sender_username = sender_member.username
        logger.info("Clan message from %s (ID:%s) in clan '%s': '%s'", sender_username, sender_id, clan.name, message)

        # Send message to all clan members
        if self.map_manager:
            for member_id in clan.members:
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    full_message = f"[Clan] {sender_username}: {message}"
                    logger.debug("Sending clan message to member %s: '%s'", member_id, full_message)
                    await member_sender.send_console_msg(
                        full_message,
                        font_color=7,  # FONTTYPE_PARTY (verde para clan)
                    )

        return ""
