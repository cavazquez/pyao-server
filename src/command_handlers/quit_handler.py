"""Handler para comando de desconexión."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.quit_command import QuitCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService

logger = logging.getLogger(__name__)


class QuitCommandHandler(CommandHandler):
    """Handler para comando de desconexión (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository | None,
        map_manager: MapManager | None,
        message_sender: MessageSender,
        npc_service: NPCService | None = None,
        summon_service: SummonService | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            message_sender: Enviador de mensajes.
            npc_service: Servicio de NPCs (opcional, para limpiar mascotas).
            summon_service: Servicio de invocación (opcional, para limpiar mascotas).
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender
        self.npc_service = npc_service
        self.summon_service = summon_service

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de desconexión (solo lógica de negocio).

        Args:
            command: Comando de desconexión.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, QuitCommand):
            return CommandResult.error("Comando inválido: se esperaba QuitCommand")

        user_id = command.user_id
        username = command.username

        logger.info(
            "QuitCommandHandler: jugador %d (%s) solicitó desconexión desde %s",
            user_id,
            username,
            self.message_sender.connection.address,
        )

        try:
            # Obtener posición del jugador antes de removerlo
            if self.player_repo and self.map_manager:
                position = await self.player_repo.get_position(user_id)
                if position:
                    map_id = position["map"]

                    # Notificar a otros jugadores en el mapa que el personaje se fue
                    other_senders = self.map_manager.get_all_message_senders_in_map(
                        map_id, exclude_user_id=user_id
                    )
                    for sender in other_senders:
                        await sender.send_character_remove(user_id)

                    logger.debug(
                        "CHARACTER_REMOVE enviado a %d jugadores en mapa %d",
                        len(other_senders),
                        map_id,
                    )

            # Limpiar mascotas del jugador
            if self.summon_service and self.npc_service:
                try:
                    pet_instance_ids = await self.summon_service.remove_all_player_pets(user_id)
                    # Remover cada mascota del mundo
                    for pet_instance_id in pet_instance_ids:
                        all_npcs = await self.npc_service.npc_repository.get_all_npcs()
                        pet_npc = next(
                            (npc for npc in all_npcs if npc.instance_id == pet_instance_id), None
                        )
                        if pet_npc:
                            await self.npc_service.remove_npc(pet_npc)
                            logger.info(
                                "Mascota removida al desconectar: user_id=%d, mascota=%s",
                                user_id,
                                pet_npc.name,
                            )
                except Exception:
                    logger.exception(
                        "Error al limpiar mascotas del jugador %d al desconectar", user_id
                    )

            # Remover jugador del MapManager
            if self.map_manager:
                self.map_manager.remove_player_from_all_maps(user_id)
                logger.debug("Jugador %d removido del MapManager", user_id)

            # Cerrar la conexión
            self.message_sender.connection.close()
            await self.message_sender.connection.wait_closed()
            logger.info("Jugador %d (%s) desconectado correctamente", user_id, username)

            return CommandResult.ok(data={"user_id": user_id, "username": username})

        except Exception:
            logger.exception("Error al procesar desconexión")
            return CommandResult.error("Error interno al procesar desconexión")
