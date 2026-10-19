"""Servicio para manejar la muerte de NPCs."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.models.party import Party

logger = logging.getLogger(__name__)
config_manager = ConfigManager()


if TYPE_CHECKING:
    from src.services.npc.npc_death_service import NPCDeathService


class ExperienceComponent:
    """Coordina experience sin cambiar la fachada existente."""

    def __init__(self, owner: NPCDeathService) -> None:
        """Conserva el contexto y las dependencias del servicio propietario."""
        self.owner = owner

    async def give_experience(
        self, user_id: int, experience: int, message_sender: MessageSender, npc: NPC
    ) -> None:
        """Otorga experiencia al jugador o distribuye a party si está en una.

        Args:
            user_id: ID del jugador que mató al NPC.
            experience: Cantidad de experiencia total.
            message_sender: MessageSender del jugador.
            npc: NPC que fue matado (para obtener posición).
        """
        # Verificar si el jugador está en party
        if self.owner.party_service:
            party = await self.owner.party_service.get_party_info(user_id)
            if party:
                await self.distribute_party_experience(user_id, experience, npc, party)
                return

        # Si no está en party, dar experiencia directamente
        await self.give_solo_experience(user_id, experience, message_sender)

    async def distribute_party_experience(
        self, user_id: int, experience: int, npc: NPC, party: Party
    ) -> None:
        """Distribuye experiencia a todos los miembros de la party.

        Args:
            user_id: ID del jugador que mató al NPC.
            experience: Cantidad de experiencia total.
            npc: NPC que fue matado.
            party: Objeto Party con los miembros.
        """
        # Distribuir experiencia a party
        if not self.owner.party_service:
            return
        distributed_exp = await self.owner.party_service.distribute_experience(
            earner_id=user_id,
            exp_amount=experience,
            map_id=npc.map_id,
            x=npc.x,
            y=npc.y,
        )

        # Actualizar experiencia de cada miembro que recibió exp
        for member_id, exp_amount in distributed_exp.items():
            await self.update_member_experience(member_id, exp_amount, user_id, npc, experience)

        # Notificar a todos los miembros de party sobre el kill
        await self.notify_party_kill(party, user_id, npc)

        logger.info(
            "Experiencia distribuida en party: %d EXP total, %d miembros recibieron",
            experience,
            len(distributed_exp),
        )

    async def update_member_experience(
        self, member_id: int, exp_amount: float, killer_id: int, npc: NPC, total_exp: int
    ) -> None:
        """Actualiza la experiencia de un miembro de party.

        Args:
            member_id: ID del miembro.
            exp_amount: Cantidad de experiencia recibida.
            killer_id: ID del jugador que mató al NPC.
            npc: NPC que fue matado.
            total_exp: Experiencia total ganada.
        """
        experience_data = await self.owner.player_repo.get_experience(member_id)
        current_exp = experience_data[0]
        current_level = await self.owner.player_repo.get_level(member_id)
        new_exp = current_exp + int(exp_amount)

        await self.owner.player_repo.update_experience(member_id, new_exp)

        # Enviar actualización al miembro
        member_sender = self.owner.map_manager.get_player_message_sender(member_id)
        if member_sender:
            await member_sender.send_update_exp(new_exp)
            if member_id == killer_id:
                # Mensaje especial para el killer
                msg = (
                    f"¡Has matado a {npc.name}! "
                    f"Tu party ganó {total_exp} EXP "
                    f"(tú recibiste {int(exp_amount)})."
                )
                await member_sender.send_console_msg(msg)
            else:
                # Mensaje para otros miembros
                await member_sender.send_console_msg(
                    f"Tu party mató a {npc.name}. Ganaste {int(exp_amount)} EXP."
                )

        logger.info(
            "Miembro de party %d ganó %d de experiencia (total: %d)",
            member_id,
            int(exp_amount),
            new_exp,
        )

        # Verificar y manejar level up
        if member_sender:
            await self.check_and_handle_level_up(member_id, current_level, new_exp, member_sender)

    async def notify_party_kill(self, party: Party, killer_id: int, npc: NPC) -> None:
        """Notifica a todos los miembros de party sobre un kill.

        Args:
            party: Objeto Party con los miembros.
            killer_id: ID del jugador que mató al NPC.
            npc: NPC que fue matado.
        """
        if not self.owner.map_manager:
            return

        for member_id in party.member_ids:
            if member_id != killer_id:  # El killer ya recibió su mensaje
                member_sender = self.owner.map_manager.get_player_message_sender(member_id)
                if member_sender:
                    # Notificar que la party mató al NPC
                    await member_sender.send_console_msg(
                        f"Tu party mató a {npc.name}.",
                        font_color=7,  # FONTTYPE_PARTY
                    )

    async def give_solo_experience(
        self, user_id: int, experience: int, message_sender: MessageSender
    ) -> None:
        """Otorga experiencia a un jugador que no está en party.

        Args:
            user_id: ID del jugador.
            experience: Cantidad de experiencia.
            message_sender: MessageSender del jugador.
        """
        experience_data = await self.owner.player_repo.get_experience(user_id)
        current_exp = experience_data[0]
        current_level = await self.owner.player_repo.get_level(user_id)
        new_exp = current_exp + experience

        await self.owner.player_repo.update_experience(user_id, new_exp)
        await message_sender.send_update_exp(new_exp)

        logger.info("Jugador %d ganó %d de experiencia (total: %d)", user_id, experience, new_exp)

        # Verificar y manejar level up
        await self.check_and_handle_level_up(user_id, current_level, new_exp, message_sender)

    async def check_and_handle_level_up(
        self,
        user_id: int,
        _current_level: int,
        _new_experience: int,
        message_sender: MessageSender,
    ) -> None:
        """Confirma crecimiento y puntos desde el estado Redis más reciente."""
        from src.services.player_progression import advance_player_level  # ruff: ignore[import-outside-top-level]

        result = await advance_player_level(self.owner.player_repo, user_id, message_sender)
        if self.owner.party_service and result["level"] > result["previous_level"]:
            await self.owner.party_service.update_member_level(user_id, int(result["level"]))
