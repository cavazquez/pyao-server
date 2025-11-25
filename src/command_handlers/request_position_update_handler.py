"""Handler para comando de solicitud de actualización de posición."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.request_position_update_command import RequestPositionUpdateCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class RequestPositionUpdateCommandHandler(CommandHandler):
    """Handler para comando de solicitud de actualización de posición (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de solicitud de actualización de posición (solo lógica de negocio).

        Args:
            command: Comando de solicitud de actualización de posición.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, RequestPositionUpdateCommand):
            return CommandResult.error("Comando inválido: se esperaba RequestPositionUpdateCommand")

        user_id = command.user_id

        logger.debug(
            "RequestPositionUpdateCommandHandler: solicitud de posición para user_id %d", user_id
        )

        try:
            # Obtener posición actual del jugador desde Redis
            position = await self.player_repo.get_position(user_id)

            if position is None:
                logger.warning("No se encontró posición para user_id %d", user_id)
                # Enviar posición por defecto
                await self.message_sender.send_pos_update(50, 50)
                return CommandResult.ok(
                    data={"user_id": user_id, "x": 50, "y": 50, "default": True}
                )

            # Enviar actualización de posición al cliente
            await self.message_sender.send_pos_update(position["x"], position["y"])
            logger.debug(
                "Posición enviada a user_id %d: (%d, %d)",
                user_id,
                position["x"],
                position["y"],
            )

            return CommandResult.ok(
                data={
                    "user_id": user_id,
                    "x": position["x"],
                    "y": position["y"],
                    "map": position.get("map"),
                }
            )

        except Exception:
            logger.exception("Error al procesar solicitud de actualización de posición")
            return CommandResult.error("Error interno al procesar actualización de posición")
