"""Handler para comando de solicitud de estadísticas."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.request_stats_command import RequestStatsCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class RequestStatsCommandHandler(CommandHandler):
    """Handler para comando de solicitud de estadísticas (solo lógica de negocio)."""

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
        """Ejecuta el comando de solicitud de estadísticas (solo lógica de negocio).

        Args:
            command: Comando de solicitud de estadísticas.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, RequestStatsCommand):
            return CommandResult.error("Comando inválido: se esperaba RequestStatsCommand")

        user_id = command.user_id

        logger.info(
            "RequestStatsCommandHandler: solicitud de estadísticas para user_id %d", user_id
        )

        try:
            # Obtener estadísticas del jugador
            stats = await self.player_repo.get_stats(user_id)
            if not stats:
                await self.message_sender.send_console_msg(
                    "Error: No se pudieron obtener las estadisticas"
                )
                return CommandResult.error("No se pudieron obtener las estadísticas")

            # Obtener atributos del jugador
            attributes = await self.player_repo.get_attributes(user_id)
            if not attributes:
                await self.message_sender.send_console_msg(
                    "Error: No se pudieron obtener los atributos"
                )
                return CommandResult.error("No se pudieron obtener los atributos")

            # Obtener hambre y sed
            hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)
            if not hunger_thirst:
                await self.message_sender.send_console_msg(
                    "Error: No se pudieron obtener hambre y sed"
                )
                return CommandResult.error("No se pudieron obtener hambre y sed")

            # Formatear mensaje de estadísticas
            stats_message = (
                f"--- Estadisticas ---\n"
                f"Nivel: {stats['level']}\n"
                f"Experiencia: {stats['experience']}/{stats['elu']}\n"
                f"Vida: {stats['min_hp']}/{stats['max_hp']}\n"
                f"Mana: {stats['min_mana']}/{stats['max_mana']}\n"
                f"Energia: {stats['min_sta']}/{stats['max_sta']}\n"
                f"Oro: {stats['gold']}\n"
                f"Hambre: {hunger_thirst['min_hunger']}/{hunger_thirst['max_hunger']}\n"
                f"Sed: {hunger_thirst['min_water']}/{hunger_thirst['max_water']}\n"
                f"--- Atributos ---\n"
                f"Fuerza: {attributes['strength']}\n"
                f"Agilidad: {attributes['agility']}\n"
                f"Inteligencia: {attributes['intelligence']}\n"
                f"Carisma: {attributes['charisma']}\n"
                f"Constitucion: {attributes['constitution']}"
            )

            # Enviar estadísticas línea por línea
            await self.message_sender.send_multiline_console_msg(stats_message)
            logger.info("Estadísticas enviadas para user_id %d", user_id)

            return CommandResult.ok(
                data={
                    "user_id": user_id,
                    "stats": stats,
                    "attributes": attributes,
                    "hunger_thirst": hunger_thirst,
                }
            )

        except Exception:
            logger.exception("Error al procesar solicitud de estadísticas")
            return CommandResult.error("Error interno al procesar estadísticas")
