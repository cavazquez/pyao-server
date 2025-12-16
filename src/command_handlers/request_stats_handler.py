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

    async def handle(self, command: Command) -> CommandResult:  # noqa: PLR0914
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
            # Obtener estadísticas usando métodos helper
            level = await self.player_repo.get_level(user_id)
            current_hp = await self.player_repo.get_current_hp(user_id)
            max_hp = await self.player_repo.get_max_hp(user_id)
            min_mana, max_mana = await self.player_repo.get_mana(user_id)
            min_sta, max_sta = await self.player_repo.get_stamina(user_id)
            experience, elu = await self.player_repo.get_experience(user_id)
            gold = await self.player_repo.get_gold(user_id)

            # Obtener atributos del jugador
            attributes = await self.player_repo.get_player_attributes(user_id)
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
                f"Nivel: {level}\n"
                f"Experiencia: {experience}/{elu}\n"
                f"Vida: {current_hp}/{max_hp}\n"
                f"Mana: {min_mana}/{max_mana}\n"
                f"Energia: {min_sta}/{max_sta}\n"
                f"Oro: {gold}\n"
                f"Hambre: {hunger_thirst['min_hunger']}/{hunger_thirst['max_hunger']}\n"
                f"Sed: {hunger_thirst['min_water']}/{hunger_thirst['max_water']}\n"
                f"--- Atributos ---\n"
                f"Fuerza: {attributes.strength}\n"
                f"Agilidad: {attributes.agility}\n"
                f"Inteligencia: {attributes.intelligence}\n"
                f"Carisma: {attributes.charisma}\n"
                f"Constitucion: {attributes.constitution}"
            )

            # Enviar estadísticas línea por línea
            await self.message_sender.send_multiline_console_msg(stats_message)
            logger.info("Estadísticas enviadas para user_id %d", user_id)

            # Obtener stats como dict para el resultado (compatibilidad)
            stats = await self.player_repo.get_stats(user_id)
            if not stats:
                await self.message_sender.send_console_msg(
                    "Error: No se pudieron obtener las estadísticas"
                )
                return CommandResult.error("No se pudieron obtener las estadísticas")

            attributes_dict = attributes.to_dict() if attributes else None

            return CommandResult.ok(
                data={
                    "user_id": user_id,
                    "stats": stats,
                    "attributes": attributes_dict,
                    "hunger_thirst": hunger_thirst,
                }
            )

        except Exception:
            logger.exception("Error al procesar solicitud de estadísticas")
            return CommandResult.error("Error interno al procesar estadísticas")
