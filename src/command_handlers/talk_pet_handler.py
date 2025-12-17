"""Handler especializado para comandos de mascotas."""

import logging
import time
from typing import TYPE_CHECKING

from src.constants.gameplay import MAX_PETS

if TYPE_CHECKING:
    from src.commands.talk_command import TalkCommand
    from src.messaging.message_sender import MessageSender
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService

logger = logging.getLogger(__name__)


class TalkPetHandler:
    """Handler especializado para comandos de mascotas."""

    def __init__(
        self,
        npc_service: NPCService | None,
        summon_service: SummonService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de mascotas.

        Args:
            npc_service: Servicio de NPCs.
            summon_service: Servicio de invocación.
            message_sender: Enviador de mensajes.
        """
        self.npc_service = npc_service
        self.summon_service = summon_service
        self.message_sender = message_sender

    async def handle_pet_command(self, user_id: int, command: TalkCommand) -> None:
        """Maneja los comandos relacionados con mascotas.

        Args:
            user_id: ID del usuario.
            command: Comando de chat.
        """
        if not self.summon_service or not self.npc_service:
            await self.message_sender.send_console_msg(
                "El sistema de mascotas no está disponible.",
                font_color=1,
            )
            return

        parsed = command.parse_pet_command()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Uso: /PET [LIBERAR|INFO]",
                font_color=1,
            )
            return

        _, args = parsed

        # Obtener todas las mascotas del jugador
        all_npcs = await self.npc_service.npc_repository.get_all_npcs()
        player_pets = [
            npc for npc in all_npcs if npc.summoned_by_user_id == user_id and npc.summoned_until > 0
        ]

        # Comando sin argumentos o con "INFO" - mostrar información
        if not args or (args and args[0].upper() == "INFO"):
            if not player_pets:
                await self.message_sender.send_console_msg(
                    "No tienes mascotas invocadas.",
                    font_color=7,
                )
                return

            current_time = time.time()

            pet_info_lines = [f"--- Mascotas ({len(player_pets)}/{MAX_PETS}) ---"]

            for i, pet in enumerate(player_pets, start=1):
                time_remaining = max(0, int(pet.summoned_until - current_time))
                minutes = time_remaining // 60
                seconds = time_remaining % 60
                pet_info_lines.append(
                    f"{i}. {pet.name} (HP: {pet.hp}/{pet.max_hp}) - Expira en {minutes}m {seconds}s"
                )

            await self.message_sender.send_multiline_console_msg("\n".join(pet_info_lines))
            return

        # Comando "LIBERAR" - liberar todas las mascotas
        if args and args[0].upper() == "LIBERAR":
            if not player_pets:
                await self.message_sender.send_console_msg(
                    "No tienes mascotas para liberar.",
                    font_color=7,
                )
                return

            released_count = 0
            for pet in player_pets:
                try:
                    await self.npc_service.remove_npc(pet)
                    released_count += 1
                    logger.info(
                        "Mascota liberada por comando: user_id=%d, mascota=%s",
                        user_id,
                        pet.name,
                    )
                except Exception:
                    logger.exception(
                        "Error al liberar mascota %s para user_id %d",
                        pet.instance_id,
                        user_id,
                    )

            if released_count > 0:
                await self.message_sender.send_console_msg(
                    f"Has liberado {released_count} mascota(s).",
                    font_color=7,
                )
            else:
                await self.message_sender.send_console_msg(
                    "No se pudieron liberar las mascotas.",
                    font_color=1,
                )
            return

        # Comando desconocido
        await self.message_sender.send_console_msg(
            "Uso: /PET [LIBERAR|INFO]",
            font_color=1,
        )
