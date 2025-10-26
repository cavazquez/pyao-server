"""Task para manejar el packet SPELL_INFO (35)."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:  # pragma: no cover - hints only
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.spellbook_repository import SpellbookRepository


logger = logging.getLogger(__name__)

MAX_SPELL_SLOTS = 35


class TaskSpellInfo(Task):
    """Envía información detallada del hechizo solicitado."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        spellbook_repo: SpellbookRepository | None = None,
        spell_catalog: SpellCatalog | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        *,
        slot: int | None = None,
    ) -> None:
        """Configura la task con dependencias opcionales y datos de sesión."""
        super().__init__(data, message_sender)
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog
        self.session_data = session_data or {}
        self._validated_slot = slot

    async def execute(self) -> None:
        """Procesa la solicitud y envía la información del hechizo al cliente."""
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("TaskSpellInfo: intento sin sesión activa")
            return

        if not self.spellbook_repo or not self.spell_catalog:
            logger.error("TaskSpellInfo: dependencias no configuradas")
            return

        slot = self._validated_slot
        if slot is None:
            reader = PacketReader(self.data)
            validator = PacketValidator(reader)
            slot = validator.read_slot(min_slot=1, max_slot=MAX_SPELL_SLOTS)

            if validator.has_errors() or slot is None:
                await self.message_sender.send_console_msg("¡Primero selecciona el hechizo!")
                return

        spell_id = await self.spellbook_repo.get_spell_in_slot(user_id, slot)
        if not spell_id:
            logger.debug("TaskSpellInfo: slot vacío user_id=%d slot=%d", user_id, slot)
            await self.message_sender.send_console_msg("¡Primero selecciona el hechizo!")
            return

        spell_data = self.spell_catalog.get_spell_data(spell_id)
        if not spell_data:
            logger.warning(
                "TaskSpellInfo: spell_id sin datos user_id=%d slot=%d spell_id=%d",
                user_id,
                slot,
                spell_id,
            )
            await self.message_sender.send_console_msg("Datos del hechizo no disponibles.")
            return

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
            "TaskSpellInfo: user_id=%d slot=%d spell_id=%d - info enviada",
            user_id,
            slot,
            spell_id,
        )
