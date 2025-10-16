"""Tarea para lanzar hechizos."""

import logging
import struct
from typing import TYPE_CHECKING

from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository
    from src.spell_service import SpellService

logger = logging.getLogger(__name__)


class TaskCastSpell(Task):
    """Maneja el lanzamiento de hechizos."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        spell_service: SpellService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de lanzar hechizo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            spell_service: Servicio de hechizos.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.spell_service = spell_service
        self.session_data = session_data or {}

    async def execute(self) -> None:  # noqa: C901
        """Ejecuta el lanzamiento de hechizo."""
        # Parsear el packet: PacketID (1 byte) + Slot (1 byte)
        min_packet_size = 2
        if len(self.data) < min_packet_size:
            logger.warning("Packet CAST_SPELL inválido: tamaño incorrecto")
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de lanzar hechizo sin estar logueado")
            return

        if not self.player_repo or not self.spell_service:
            logger.error("Dependencias no disponibles para lanzar hechizo")
            return

        try:
            # Extraer el slot del hechizo (segundo byte)
            slot = struct.unpack("B", self.data[1:2])[0]

            logger.info("user_id %d intenta lanzar hechizo en slot %d", user_id, slot)

            # Obtener el hechizo del jugador en ese slot
            # Por ahora, asumimos que el slot 1 = Dardo Mágico (spell_id=1)
            # TODO: Implementar sistema de libro de hechizos en Redis
            if slot != 1:
                await self.message_sender.send_console_msg("No tienes ese hechizo.")
                return

            spell_id = 1  # Dardo Mágico

            # Obtener posición del jugador para determinar target
            position = await self.player_repo.get_position(user_id)
            if not position:
                return

            # Por ahora, el target es la posición frente al jugador
            # TODO: Implementar selección de target desde el cliente
            heading = position["heading"]
            target_x = position["x"]
            target_y = position["y"]

            # Calcular posición del target según heading
            if heading == 1:  # Norte
                target_y -= 1
            elif heading == 2:  # Este  # noqa: PLR2004
                target_x += 1
            elif heading == 3:  # Sur  # noqa: PLR2004
                target_y += 1
            elif heading == 4:  # Oeste  # noqa: PLR2004
                target_x -= 1

            # Lanzar el hechizo
            success = await self.spell_service.cast_spell(
                user_id, spell_id, target_x, target_y, self.message_sender
            )

            if not success:
                logger.debug("Fallo al lanzar hechizo")

        except struct.error:
            logger.exception("Error al parsear packet CAST_SPELL")
