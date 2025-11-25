"""Handler para comando de lanzar hechizo."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.cast_spell_command import CastSpellCommand
from src.services.player.stamina_service import STAMINA_COST_SPELL

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.spellbook_repository import SpellbookRepository
    from src.services.player.spell_service import SpellService
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)

# Constantes para validación de coordenadas
MAX_COORD = 100
MAX_SPELL_RANGE = 10


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

    async def handle(self, command: Command) -> CommandResult:  # noqa: PLR0915
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

        # Validar dependencias
        if not self.player_repo or not self.spell_service or not self.spellbook_repo:
            logger.error("Dependencias no disponibles para lanzar hechizo")
            return CommandResult.error("Error interno: dependencias no disponibles")

        # Consumir stamina por lanzar hechizo
        if self.stamina_service:
            can_cast = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_SPELL,
                message_sender=self.message_sender,
            )

            if not can_cast:
                logger.debug("user_id %d no tiene suficiente stamina para lanzar hechizo", user_id)
                return CommandResult.error("No tienes suficiente stamina para lanzar el hechizo.")

        try:
            # Validar coordenadas si vienen en el comando
            if target_x is not None and target_y is not None:
                if target_x < 1 or target_x > MAX_COORD or target_y < 1 or target_y > MAX_COORD:
                    await self.message_sender.send_console_msg("Coordenadas inválidas")
                    return CommandResult.error("Coordenadas inválidas")

                logger.info(
                    "user_id %d intenta lanzar hechizo desde slot %d hacia (%d, %d)",
                    user_id,
                    slot,
                    target_x,
                    target_y,
                )
            else:
                logger.info(
                    "user_id %d intenta lanzar hechizo desde slot %d (formato antiguo)",
                    user_id,
                    slot,
                )

            # Obtener el hechizo del jugador en ese slot desde Redis
            spell_id = await self.spellbook_repo.get_spell_in_slot(user_id, slot)
            if spell_id is None:
                await self.message_sender.send_console_msg("No tienes ese hechizo.")
                logger.warning("user_id %d no tiene hechizo en slot %d (slot vacío)", user_id, slot)
                return CommandResult.error("No tienes ese hechizo.")

            # Obtener posición del jugador
            position = await self.player_repo.get_position(user_id)
            if not position:
                logger.warning("No se encontró posición para user_id %d", user_id)
                return CommandResult.error("Posición no encontrada")

            player_x = position["x"]
            player_y = position["y"]

            # Si no hay coordenadas del target, calcular según heading
            if target_x is None or target_y is None:
                heading = position["heading"]
                target_x = player_x
                target_y = player_y

                # Calcular posición del target según heading
                if heading == 1:  # Norte
                    target_y -= 1
                elif heading == 2:  # Este  # noqa: PLR2004
                    target_x += 1
                elif heading == 3:  # Sur  # noqa: PLR2004
                    target_y += 1
                elif heading == 4:  # Oeste  # noqa: PLR2004
                    target_x -= 1

                logger.debug(
                    "Target calculado según heading %d: (%d, %d)", heading, target_x, target_y
                )

            logger.info(
                "user_id %d lanzará hechizo spell_id=%d desde slot %d hacia (%d, %d)",
                user_id,
                spell_id,
                slot,
                target_x,
                target_y,
            )

            # Validar que el target esté en rango (máximo 10 tiles)
            distance = abs(target_x - player_x) + abs(target_y - player_y)  # Manhattan distance

            if distance > MAX_SPELL_RANGE:
                await self.message_sender.send_console_msg(
                    "El objetivo está demasiado lejos para lanzar el hechizo."
                )
                logger.debug(
                    "user_id %d intentó lanzar hechizo fuera de rango: distancia=%d",
                    user_id,
                    distance,
                )
                return CommandResult.error(
                    "El objetivo está demasiado lejos para lanzar el hechizo."
                )

            # Lanzar el hechizo
            success = await self.spell_service.cast_spell(
                user_id, spell_id, target_x, target_y, self.message_sender
            )

            if not success:
                logger.debug("Fallo al lanzar hechizo")
                return CommandResult.error("Fallo al lanzar el hechizo.")

            return CommandResult.ok(
                data={
                    "spell_id": spell_id,
                    "target_x": target_x,
                    "target_y": target_y,
                    "slot": slot,
                }
            )

        except Exception as e:
            logger.exception("Error al lanzar hechizo")
            return CommandResult.error(f"Error al lanzar hechizo: {e!s}")
