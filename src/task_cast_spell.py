"""Tarea para lanzar hechizos."""

import logging
import struct
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.spellbook_repository import SpellbookRepository
from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository
    from src.spell_service import SpellService
    from src.spellbook_repository import SpellbookRepository

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
        session_data: dict[str, dict[str, int]] | None = None,
        spellbook_repo: SpellbookRepository | None = None,
    ) -> None:
        """Inicializa la tarea de lanzar hechizo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            spell_service: Servicio de hechizos.
            session_data: Datos de sesión.
            spellbook_repo: Repositorio de libro de hechizos.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.spell_service = spell_service
        self.session_data = session_data or {}
        self.spellbook_repo = spellbook_repo

    async def execute(self) -> None:
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

        try:
            # Extraer el slot del hechizo (segundo byte)
            slot = struct.unpack("B", self.data[1:2])[0]

            # Determinar si el packet incluye coordenadas del target
            has_target_coords = len(self.data) >= PACKET_SIZE_WITH_COORDS

            if has_target_coords:
                # Formato nuevo: coordenadas del target incluidas
                target_x, target_y = struct.unpack("<HH", self.data[2:6])  # Little-endian uint16
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

        except struct.error:
            logger.exception("Error al parsear packet CAST_SPELL")
