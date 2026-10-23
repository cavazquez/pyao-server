"""Handler especializado para comandos de mascotas."""

import logging
import time
from typing import TYPE_CHECKING

from src.constants.gameplay import MAX_PETS
from src.services.world.pets import PetOrders
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id

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
        self.pet_orders = PetOrders(npc_service) if npc_service is not None else None

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
                "Uso: /PET [LIBERAR|INFO|SEGUIR|ESPERAR]",
                font_color=1,
            )
            return

        _, args = parsed

        player_pets = await self.npc_service.npc_repository.get_player_pets(user_id)

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

        if args and args[0].upper() in {"SEGUIR", "ESPERAR"} and self.pet_orders:
            order = "follow" if args[0].upper() == "SEGUIR" else "wait"
            changed = 0
            for pet in player_pets:
                result = await self.pet_orders.command(
                    user_id, pet.instance_id, order, operation_id()
                )
                changed += int(bool(result["applied"]))
            if changed:
                await require_durable(self.npc_service.npc_repository.redis.redis)
            await self.message_sender.send_console_msg(f"Orden aplicada a {changed} mascota(s).")
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
                    if self.pet_orders:
                        result = await self.pet_orders.command(
                            user_id, pet.instance_id, "release", operation_id()
                        )
                        released_count += int(bool(result["applied"]))
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
            "Uso: /PET [LIBERAR|INFO|SEGUIR|ESPERAR]",
            font_color=1,
        )
