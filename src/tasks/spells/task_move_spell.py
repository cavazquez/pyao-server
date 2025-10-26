"""Task para mover hechizos dentro del libro del jugador."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.network.session_manager import SessionManager
from src.tasks.task import Task

MIN_PACKET_LENGTH = 3

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.spellbook_repository import MoveSpellResult, SpellbookRepository


logger = logging.getLogger(__name__)


class TaskMoveSpell(Task):
    """Intercambia un hechizo con su slot adyacente."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int | None = None,
        upwards: bool | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        spellbook_repo: SpellbookRepository | None = None,
        spell_catalog: SpellCatalog | None = None,
    ) -> None:
        """Crea la task con sus dependencias opcionales."""
        super().__init__(data, message_sender)
        self.slot = slot
        self.upwards = upwards
        self.session_data = session_data or {}
        self.spellbook_repo = spellbook_repo
        self.spell_catalog = spell_catalog

        if self.slot is None or self.upwards is None:
            self._parse_payload(data)

    async def execute(self) -> None:
        """Intercambia slots si los datos y la sesión son válidos."""
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning("Intento de mover hechizo sin usuario logueado")
            return

        if not self.spellbook_repo:
            logger.error("SpellbookRepository no disponible para mover hechizos")
            return

        if self.slot is None or self.upwards is None:
            logger.warning("Packet MOVE_SPELL inválido: falta información de movimiento")
            return

        try:
            result = await self.spellbook_repo.move_spell(
                user_id=user_id,
                slot=self.slot,
                upwards=self.upwards,
            )
        except Exception:  # pragma: no cover - el repositorio ya loguea
            logger.exception("Error inesperado moviendo hechizo")
            return

        if result is None:
            # Redis no disponible, ya se logueó en el repo
            return

        if not result.success:
            if result.reason in {"out_of_bounds", "invalid_slot"}:
                await self.message_sender.send_console_msg(
                    "No puedes mover el hechizo en esa dirección.",
                )
            return

        await self._send_slot_update(user_id, result)

    def _parse_payload(self, data: bytes) -> None:
        """Extrae slot y dirección del packet sin prevalidación."""
        if len(data) < MIN_PACKET_LENGTH:
            logger.warning("Packet MOVE_SPELL demasiado corto: len=%d", len(data))
            self.slot = None
            self.upwards = None
            return

        upwards_flag = data[1]
        slot = data[2]

        self.upwards = upwards_flag != 0
        self.slot = slot

    async def _send_slot_update(self, user_id: int, result: MoveSpellResult) -> None:
        """Envía los slots involucrados en el intercambio."""
        await self._send_single_slot(user_id, result.slot, result.slot_spell_id)
        await self._send_single_slot(user_id, result.target_slot, result.target_slot_spell_id)

    async def _send_single_slot(
        self,
        user_id: int,
        slot: int,
        spell_id: int | None,
    ) -> None:
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
