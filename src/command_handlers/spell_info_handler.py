"""Handler para comando de información de hechizos."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.spell_info_command import SpellInfoCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.spellbook_repository import SpellbookRepository

logger = logging.getLogger(__name__)


class SpellInfoCommandHandler(CommandHandler):
    """Handler para comando de información de hechizos (solo lógica de negocio)."""

    def __init__(
        self,
        spellbook_repo: SpellbookRepository,
        spell_catalog: SpellCatalog,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            spellbook_repo: Repositorio de libro de hechizos.
            spell_catalog: Catálogo de hechizos.
            message_sender: Enviador de mensajes.
        """
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de información de hechizos (solo lógica de negocio).

        Args:
            command: Comando de información de hechizos.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, SpellInfoCommand):
            return CommandResult.error("Comando inválido: se esperaba SpellInfoCommand")

        user_id = command.user_id
        slot = command.slot

        logger.info(
            "SpellInfoCommandHandler: solicitud de información de hechizo para user_id %d slot %d",
            user_id,
            slot,
        )

        try:
            spell_id = await self.spellbook_repo.get_spell_in_slot(user_id, slot)
            if not spell_id:
                logger.debug(
                    "SpellInfoCommandHandler: slot vacío user_id=%d slot=%d", user_id, slot
                )
                await self.message_sender.send_console_msg("¡Primero selecciona el hechizo!")
                return CommandResult.error("Slot vacío")

            spell_data = self.spell_catalog.get_spell_data(spell_id)
            if not spell_data:
                logger.warning(
                    "SpellInfoCommandHandler: spell_id sin datos user_id=%d slot=%d spell_id=%d",
                    user_id,
                    slot,
                    spell_id,
                )
                await self.message_sender.send_console_msg("Datos del hechizo no disponibles.")
                return CommandResult.error("Datos del hechizo no disponibles")

            name = spell_data.get("name", f"Hechizo {spell_id}")
            description = spell_data.get("description", "Sin descripción.")
            min_skill = spell_data.get("min_skill", 0)
            mana_cost = spell_data.get("mana_cost", 0)
            stamina_cost = spell_data.get("stamina_cost", 0)

            lines = [
                "%%%%%%%%%%%% INFO DEL HECHIZO %%%%%%%%%%%%",
                f"Nombre: {name}",
                f"Descripción: {description}",
                f"Skill requerido: {min_skill} de magia.",
                f"Maná necesario: {mana_cost}",
                f"Energía necesaria: {stamina_cost}",
                "%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%",
            ]

            await self.message_sender.send_multiline_console_msg("\n".join(lines))
            logger.info(
                "SpellInfoCommandHandler: user_id=%d slot=%d spell_id=%d - info enviada",
                user_id,
                slot,
                spell_id,
            )

            return CommandResult.ok(
                data={
                    "user_id": user_id,
                    "slot": slot,
                    "spell_id": spell_id,
                    "spell_data": spell_data,
                }
            )

        except Exception:
            logger.exception("Error al procesar solicitud de información de hechizo")
            return CommandResult.error("Error interno al procesar información de hechizo")
