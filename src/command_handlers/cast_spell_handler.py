"""Handler para comando de lanzar hechizo."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.cast_spell_execution_handler import CastSpellExecutionHandler
from src.command_handlers.cast_spell_validation_handler import CastSpellValidationHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.cast_spell_command import CastSpellCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.spellbook_repository import SpellbookRepository
    from src.services.player.spell_service import SpellService
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)


class CastSpellCommandHandler(CommandHandler):
    """Handler para comando de lanzar hechizo (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        spell_service: SpellService,
        spellbook_repo: SpellbookRepository,
        stamina_service: StaminaService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            spell_service: Servicio de hechizos.
            spellbook_repo: Repositorio de libro de hechizos.
            stamina_service: Servicio de stamina.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.spell_service = spell_service
        self.spellbook_repo = spellbook_repo
        self.stamina_service = stamina_service
        self.message_sender = message_sender

        # Inicializar handlers especializados
        self.validation_handler = CastSpellValidationHandler(
            player_repo=player_repo,
            spellbook_repo=spellbook_repo,
            stamina_service=stamina_service,
            message_sender=message_sender,
        )

        self.execution_handler = CastSpellExecutionHandler(
            player_repo=player_repo,
            spell_service=spell_service,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de lanzar hechizo (solo lógica de negocio).

        Args:
            command: Comando de lanzar hechizo.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, CastSpellCommand):
            return CommandResult.error("Comando inválido: se esperaba CastSpellCommand")

        user_id = command.user_id
        slot = command.slot
        target_x = command.target_x
        target_y = command.target_y

        logger.debug(
            "CastSpellCommandHandler: Procesando hechizo user_id=%d slot=%d target=(%s, %s)",
            user_id,
            slot,
            target_x,
            target_y,
        )

        try:
            # Validar dependencias
            is_valid, error_msg = await self.validation_handler.validate_dependencies()
            if not is_valid:
                return CommandResult.error(error_msg or "Error interno")

            # Validar stamina
            is_valid, error_msg = await self.validation_handler.validate_stamina(user_id)
            if not is_valid:
                return CommandResult.error(error_msg or "No tienes suficiente stamina")

            # Validar coordenadas
            is_valid, error_msg = self.validation_handler.validate_coordinates(target_x, target_y)
            if not is_valid:
                await self.message_sender.send_console_msg(error_msg or "Coordenadas inválidas")
                return CommandResult.error(error_msg or "Coordenadas inválidas")

            # Validar spell slot
            is_valid, error_msg, spell_id = await self.validation_handler.validate_spell_slot(
                user_id, slot
            )
            if not is_valid or spell_id is None:
                await self.message_sender.send_console_msg(error_msg or "No tienes ese hechizo.")
                return CommandResult.error(error_msg or "No tienes ese hechizo.")

            # Calcular target
            target_coords = await self.execution_handler.calculate_target(
                user_id, target_x, target_y
            )
            if not target_coords:
                return CommandResult.error("Posición no encontrada")

            final_target_x, final_target_y = target_coords

            logger.info(
                "user_id %d lanzará hechizo spell_id=%d desde slot %d hacia (%d, %d)",
                user_id,
                spell_id,
                slot,
                final_target_x,
                final_target_y,
            )

            # Obtener posición del jugador para validar rango
            position = await self.player_repo.get_position(user_id)
            if not position:
                return CommandResult.error("Posición no encontrada")

            player_x = position["x"]
            player_y = position["y"]

            # Validar rango
            is_valid, error_msg = self.validation_handler.validate_range(
                player_x, player_y, final_target_x, final_target_y
            )
            if not is_valid:
                await self.message_sender.send_console_msg(
                    error_msg or "El objetivo está demasiado lejos para lanzar el hechizo."
                )
                return CommandResult.error(
                    error_msg or "El objetivo está demasiado lejos para lanzar el hechizo."
                )

            # Ejecutar hechizo
            success, error_msg = await self.execution_handler.execute_spell(
                user_id, spell_id, final_target_x, final_target_y
            )
            if not success:
                return CommandResult.error(error_msg or "Fallo al lanzar el hechizo.")

            return CommandResult.ok(
                data={
                    "spell_id": spell_id,
                    "target_x": final_target_x,
                    "target_y": final_target_y,
                    "slot": slot,
                }
            )

        except Exception as e:
            logger.exception("Error al lanzar hechizo")
            return CommandResult.error(f"Error al lanzar hechizo: {e!s}")
