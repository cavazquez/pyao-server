"""Handler para comando de solicitud de habilidades."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.request_skills_command import RequestSkillsCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class RequestSkillsCommandHandler(CommandHandler):
    """Handler para comando de solicitud de habilidades (solo lógica de negocio)."""

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
        """Ejecuta el comando de solicitud de habilidades (solo lógica de negocio).

        Args:
            command: Comando de solicitud de habilidades.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, RequestSkillsCommand):
            return CommandResult.error("Comando inválido: se esperaba RequestSkillsCommand")

        user_id = command.user_id

        logger.info(
            "RequestSkillsCommandHandler: solicitud de habilidades para user_id %d", user_id
        )

        try:
            # Obtener habilidades del jugador
            skills = await self.player_repo.get_skills(user_id)
            if not skills:
                logger.warning("No se encontraron habilidades para user_id %d", user_id)
                # Enviar habilidades vacías o por defecto
                skills = {
                    "magia": 0,
                    "robustez": 0,
                    "agilidad": 0,
                    "talar": 0,
                    "pesca": 0,
                    "mineria": 0,
                    "herreria": 0,
                    "carpinteria": 0,
                    "supervivencia": 0,
                }

            # Enviar habilidades al cliente
            await self.message_sender.send_update_skills(
                magic=skills.get("magia", 0),
                robustness=skills.get("robustez", 0),
                agility=skills.get("agilidad", 0),
                woodcutting=skills.get("talar", 0),
                fishing=skills.get("pesca", 0),
                mining=skills.get("mineria", 0),
                blacksmithing=skills.get("herreria", 0),
                carpentry=skills.get("carpinteria", 0),
                survival=skills.get("supervivencia", 0),
            )

            logger.info("Habilidades enviadas para user_id %d", user_id)

            return CommandResult.ok(data={"user_id": user_id, "skills": skills})

        except Exception:
            logger.exception("Error al procesar solicitud de habilidades")
            return CommandResult.error("Error interno al procesar habilidades")
