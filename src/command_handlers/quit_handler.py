"""Handler para comando de desconexión."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.quit_command import QuitCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class QuitCommandHandler(CommandHandler):
    """Handler para comando de desconexión (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository | None,
        map_manager: MapManager | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

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
