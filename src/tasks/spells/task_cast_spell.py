"""Tarea para lanzar hechizos."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.session_manager import SessionManager
from src.repositories.spellbook_repository import SpellbookRepository
from src.stamina_service import STAMINA_COST_SPELL
from src.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.spell_service import SpellService
    from src.repositories.spellbook_repository import SpellbookRepository
    from src.stamina_service import StaminaService

logger = logging.getLogger(__name__)

# Tamaños de packet
PACKET_SIZE_WITH_COORDS = 6  # PacketID + Slot + X + Y
PACKET_SIZE_WITHOUT_COORDS = 2  # PacketID + Slot


class TaskCastSpell(Task):
    """Maneja el lanzamiento de hechizos."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        spell_service: SpellService | None = None,
        stamina_service: StaminaService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        spellbook_repo: SpellbookRepository | None = None,
    ) -> None:
        """Inicializa la tarea de lanzar hechizo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            spell_service: Servicio de hechizos.
            stamina_service: Servicio de stamina.
            session_data: Datos de sesión.
            spellbook_repo: Repositorio de libro de hechizos.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.spell_service = spell_service
        self.stamina_service = stamina_service
        self.session_data = session_data or {}
        self.spellbook_repo = spellbook_repo

    async def execute(  # noqa: PLR0914, PLR0915 - Método complejo por naturaleza del protocolo
        self,
    ) -> None:
        """Ejecuta el lanzamiento de hechizo."""
        # Parsear el packet: PacketID (1 byte) + Slot (1 byte) [+ X (2 bytes) + Y (2 bytes)]
        # Soporta formato antiguo (2 bytes) y nuevo (6 bytes)
        if len(self.data) < PACKET_SIZE_WITHOUT_COORDS:
            logger.warning("Packet CAST_SPELL inválido: tamaño incorrecto")
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de lanzar hechizo sin estar logueado")
            return

        if not self.player_repo or not self.spell_service or not self.spellbook_repo:
            logger.error("Dependencias no disponibles para lanzar hechizo")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        slot = validator.read_slot(min_slot=1, max_slot=35)  # Spellbook tiene más slots

        if validator.has_errors() or slot is None:
            error_msg = validator.get_error_message() if validator.has_errors() else "Slot inválido"
            await self.message_sender.send_console_msg(error_msg)
            return

        # Consumir stamina por lanzar hechizo
        if self.stamina_service:
            can_cast = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_SPELL,
                message_sender=self.message_sender,
            )

            if not can_cast:
                logger.debug("user_id %d no tiene suficiente stamina para lanzar hechizo", user_id)
                return

        try:
            # Determinar si el packet incluye coordenadas del target
            has_target_coords = len(self.data) >= PACKET_SIZE_WITH_COORDS

            if has_target_coords:
                # Formato nuevo: coordenadas del target incluidas
                # Leer coordenadas directamente con el reader (ya consumimos el slot)
                target_x = reader.read_int16()
                target_y = reader.read_int16()

                # Validar coordenadas (100 es el tamaño máximo del mapa)
                MAX_COORD = 100  # noqa: N806 - Constante local
                if target_x < 1 or target_x > MAX_COORD or target_y < 1 or target_y > MAX_COORD:
                    await self.message_sender.send_console_msg("Coordenadas inválidas")
                    return

                logger.info(
                    "user_id %d intenta lanzar hechizo desde slot %d hacia (%d, %d)",
                    user_id,
                    slot,
                    target_x,
                    target_y,
                )
            else:
                # Formato antiguo: calcular target según heading del jugador
                logger.info(
                    "user_id %d intenta lanzar hechizo desde slot %d (formato antiguo)",
                    user_id,
                    slot,
                )
                target_x = None
                target_y = None

            # Obtener el hechizo del jugador en ese slot desde Redis
            spell_id = await self.spellbook_repo.get_spell_in_slot(user_id, slot)
            if spell_id is None:
                await self.message_sender.send_console_msg("No tienes ese hechizo.")
                logger.warning("user_id %d no tiene hechizo en slot %d (slot vacío)", user_id, slot)
                return

            # Obtener posición del jugador
            position = await self.player_repo.get_position(user_id)
            if not position:
                return

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

            if distance > 10:  # noqa: PLR2004
                await self.message_sender.send_console_msg(
                    "El objetivo está demasiado lejos para lanzar el hechizo."
                )
                logger.debug(
                    "user_id %d intentó lanzar hechizo fuera de rango: distancia=%d",
                    user_id,
                    distance,
                )
                return

            # Lanzar el hechizo
            success = await self.spell_service.cast_spell(
                user_id, spell_id, target_x, target_y, self.message_sender
            )

            if not success:
                logger.debug("Fallo al lanzar hechizo")

        except Exception:
            logger.exception("Error al parsear packet CAST_SPELL")
