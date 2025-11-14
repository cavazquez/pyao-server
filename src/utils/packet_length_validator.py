"""Utilidad para validar longitud mínima de packets.

Centraliza la validación de longitud para evitar código duplicado
y proporcionar mensajes de error consistentes.
"""

import logging
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class PacketLengthValidator:
    """Validador de longitud de packets con mensajes de error descriptivos."""

    # Longitudes mínimas esperadas por packet_id
    MIN_PACKET_LENGTHS: ClassVar[dict[int, int]] = {
        # Packets sin datos (solo PacketID)
        1: 1,  # THROW_DICES
        7: 1,  # REQUEST_POSITION_UPDATE
        13: 1,  # REQUEST_ATTRIBUTES
        17: 1,  # COMMERCE_END
        21: 1,  # BANK_END
        22: 1,  # PING
        23: 1,  # AYUDA
        24: 1,  # REQUEST_STATS
        25: 1,  # INFORMATION
        27: 1,  # UPTIME
        28: 1,  # ONLINE
        29: 1,  # QUIT
        30: 1,  # MEDITATE
        32: 1,  # PICK_UP
        34: 1,  # ATTACK
        35: 1,  # TLS_HANDSHAKE
        122: 1,  # GM_COMMANDS (mínimo, varía según subcomando)
        # Packets con 1 byte de datos
        6: 2,  # WALK (heading)
        37: 2,  # CHANGE_HEADING (heading)
        # Packets con 2 bytes de datos
        2: 3,  # LOGIN (username_len + username_start)
        3: 2,  # DOUBLE_CLICK (target)
        19: 2,  # EQUIP_ITEM (slot)
        33: 4,  # WORK_LEFT_CLICK (x + y + skill)
        40: 3,  # COMMERCE_BUY (slot)
        41: 3,  # BANK_EXTRACT_ITEM (slot)
        42: 3,  # COMMERCE_SELL (slot)
        43: 3,  # BANK_DEPOSIT (slot)
        # Packets con 3 bytes de datos
        26: 3,  # LEFT_CLICK (x + y)
        # Packets con 4 bytes de datos
        15: 5,  # DROP (slot + quantity)
        39: 7,  # CAST_SPELL (slot + x + y - soporta ambos formatos)
        111: 5,  # BANK_EXTRACT_GOLD (amount)
        112: 5,  # BANK_DEPOSIT_GOLD (amount)
        # Packets con longitud variable (mínimo base)
        4: 3,  # CREATE_ACCOUNT (username_len + username_start)
        5: 3,  # TALK (message_len + message_start)
        14: 3,  # PARTY_JOIN (username_len + username_start)
        16: 3,  # PARTY_MESSAGE (message_len + message_start)
        31: 3,  # USE_ITEM (slot)
    }

    @classmethod
    async def validate_min_length(
        cls, data: bytes, packet_id: int, message_sender: MessageSender | None = None
    ) -> bool:
        """Valida que el packet tenga la longitud mínima requerida.

        Args:
            data: Datos del packet.
            packet_id: ID del packet para verificar longitud específica.
            message_sender: MessageSender opcional para enviar error al cliente.

        Returns:
            True si la longitud es válida, False en caso contrario.
        """
        if not data:
            if message_sender:
                await message_sender.send_console_msg("Error: Packet vacío")
            logger.warning("Packet vacío recibido")
            return False

        actual_length = len(data)
        min_length = cls.MIN_PACKET_LENGTHS.get(packet_id, 1)  # Por defecto mínimo 1 (PacketID)

        if actual_length < min_length:
            error_msg = (
                f"Packet truncado: se esperaban al menos {min_length} bytes, "
                f"recibidos {actual_length}"
            )
            if message_sender:
                await message_sender.send_console_msg(error_msg)
            logger.warning(
                "Packet %d truncado: esperaba >=%d, recibió %d",
                packet_id,
                min_length,
                actual_length,
            )
            return False

        return True

    @classmethod
    async def validate_generic_min_length(
        cls,
        data: bytes,
        min_length: int,
        packet_name: str,
        message_sender: MessageSender | None = None,
    ) -> bool:
        """Valida longitud mínima genérica para cualquier packet.

        Args:
            data: Datos del packet.
            min_length: Longitud mínima requerida.
            packet_name: Nombre del packet para logging.
            message_sender: MessageSender opcional para enviar error al cliente.

        Returns:
            True si la longitud es válida, False en caso contrario.
        """
        if not data:
            if message_sender:
                await message_sender.send_console_msg("Error: Packet vacío")
            logger.warning("Packet vacío recibido (%s)", packet_name)
            return False

        actual_length = len(data)
        if actual_length < min_length:
            error_msg = (
                f"Packet {packet_name} truncado: se esperaban al menos "
                f"{min_length} bytes, recibidos {actual_length}"
            )
            if message_sender:
                await message_sender.send_console_msg(error_msg)
            logger.warning(error_msg)
            return False

        return True

    @classmethod
    def get_packet_min_length(cls, packet_id: int) -> int:
        """Retorna la longitud mínima esperada para un packet_id.

        Args:
            packet_id: ID del packet.

        Returns:
            Longitud mínima esperada (1 por defecto si no está definido).
        """
        return cls.MIN_PACKET_LENGTHS.get(packet_id, 1)

    @classmethod
    def is_packet_empty(cls, data: bytes) -> bool:
        """Verifica si un packet está vacío.

        Args:
            data: Datos del packet.

        Returns:
            True si el packet está vacío, False en caso contrario.
        """
        return len(data) == 0
