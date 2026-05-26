"""Clan service mixins."""

import logging

from src.models.clan import (
    MIN_LEVEL_TO_JOIN,
    Clan,
    ClanInvitation,
    ClanMember,
    ClanRank,
)
from src.services.clan._helpers import ClanServiceHelpersMixin

logger = logging.getLogger(__name__)


class ClanMembershipMixin(ClanServiceHelpersMixin):
    """Invite, accept, reject, leave, and kick clan members."""

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

        # Notify the new member
        new_member_sender = self._get_player_message_sender(user_id)
        if new_member_sender:
            await new_member_sender.send_console_msg(
                f"Te has unido al clan '{clan.name}'",
                font_color=7,  # FONTTYPE_PARTY
            )
            logger.debug("Notificación enviada a user_id %s (se unió al clan)", user_id)
        else:
            logger.debug("No se pudo enviar notificación a user_id %s (no conectado)", user_id)

        # Notify all clan members about the new member
        new_member_username = invitation.target_username
        for member_id in clan.members:
            if member_id != user_id:  # Don't notify the new member again
                member_sender = self._get_player_message_sender(member_id)
                if member_sender:
                    await member_sender.send_console_msg(
                        f"{new_member_username} se ha unido al clan '{clan.name}'",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                    logger.debug("Notificación enviada a user_id %s (miembro del clan)", member_id)
                else:
                    logger.debug(
                        "No se pudo enviar notificación a user_id %s (no conectado)", member_id
                    )

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
