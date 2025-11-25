"""Handler para comando de mover hechizos en el libro."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.move_spell_command import MoveSpellCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.spellbook_repository import MoveSpellResult, SpellbookRepository

logger = logging.getLogger(__name__)


class MoveSpellCommandHandler(CommandHandler):
    """Handler para comando de mover hechizos (solo lógica de negocio)."""

    def __init__(
        self,
        spellbook_repo: SpellbookRepository,
        spell_catalog: SpellCatalog | None,
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
        """Ejecuta el comando de mover hechizo (solo lógica de negocio).

        Args:
            command: Comando de mover hechizo.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, MoveSpellCommand):
            return CommandResult.error("Comando inválido: se esperaba MoveSpellCommand")

        user_id = command.user_id
        slot = command.slot
        upwards = command.upwards

        logger.info(
            "MoveSpellCommandHandler: user_id=%d intenta mover hechizo slot=%d upwards=%s",
            user_id,
            slot,
            upwards,
        )

        try:
            result = await self.spellbook_repo.move_spell(
                user_id=user_id,
                slot=slot,
                upwards=upwards,
            )
        except Exception:
            logger.exception("Error inesperado moviendo hechizo")
            return CommandResult.error("Error inesperado al mover hechizo")

        if result is None:
            # Redis no disponible, ya se logueó en el repo
            return CommandResult.error("Servicio no disponible")

        if not result.success:
            error_msg = "No puedes mover el hechizo en esa dirección."
            if result.reason in {"out_of_bounds", "invalid_slot"}:
                await self.message_sender.send_console_msg(error_msg)
            return CommandResult.error(error_msg)

        # Enviar actualización de slots
        await self._send_slot_update(user_id, result)

        return CommandResult.ok(
            data={
                "slot": result.slot,
                "target_slot": result.target_slot,
                "slot_spell_id": result.slot_spell_id,
                "target_slot_spell_id": result.target_slot_spell_id,
            }
        )

    async def _send_slot_update(self, user_id: int, result: MoveSpellResult) -> None:
        """Envía los slots involucrados en el intercambio.

        Args:
            user_id: ID del jugador.
            result: Resultado del movimiento de hechizo.
        """
        await self._send_single_slot(user_id, result.slot, result.slot_spell_id)
        await self._send_single_slot(user_id, result.target_slot, result.target_slot_spell_id)

    async def _send_single_slot(
        self,
        user_id: int,
        slot: int,
        spell_id: int | None,
    ) -> None:
        """Envía actualización de un slot individual.

        Args:
            user_id: ID del jugador.
            slot: Slot a actualizar.
            spell_id: ID del hechizo (None si está vacío).
        """
        spell_id_value = spell_id or 0

        if spell_id is None:
            spell_name = "(None)"
        else:
            spell_name = ""
            if self.spell_catalog:
                spell_data = self.spell_catalog.get_spell_data(spell_id)
                spell_name = spell_data.get("name", f"Spell {spell_id}") if spell_data else ""
            if not spell_name:
                spell_name = f"Spell {spell_id}"

        await self.message_sender.send_change_spell_slot(
            slot=slot,
            spell_id=spell_id_value,
            spell_name=spell_name,
        )

        logger.debug(
            "user_id %d movió hechizo: slot=%d, spell_id=%d",
            user_id,
            slot,
            spell_id_value,
        )
