"""PacketReader para leer datos de packets de forma estructurada."""

import struct


class PacketReader:
    """Lee datos de un packet de forma secuencial y type-safe.

    Simplifica la lectura de packets eliminando código repetitivo de struct.unpack
    y manejo manual de offsets.

    Example:
        >>> reader = PacketReader(data)
        >>> slot = reader.read_byte()
        >>> quantity = reader.read_int16()
        >>> username = reader.read_string()
    """

    def __init__(self, data: bytes) -> None:
        """Inicializa el reader con los datos del packet.

        Args:
            data: Datos del packet (incluye PacketID en posición 0).
        """
        self.data = data
        self.offset = 1  # Saltar PacketID (primer byte)

    def read_byte(self) -> int:
        """Lee un uint8 (1 byte).

        Returns:
            Valor entero sin signo (0-255).
        """
        self.ensure_remaining_bytes(1, "read_byte")
        value: int = struct.unpack("B", self.data[self.offset : self.offset + 1])[0]
        self.offset += 1
        return value

    def read_int16(self) -> int:
        """Lee un int16 little-endian (2 bytes).

        Returns:
            Valor entero sin signo (0-65535).
        """
        self.ensure_remaining_bytes(2, "read_int16")
        value: int = struct.unpack("<H", self.data[self.offset : self.offset + 2])[0]
        self.offset += 2
        return value

    def read_int32(self) -> int:
        """Lee un int32 little-endian (4 bytes).

        Returns:
            Valor entero sin signo (0-4294967295).
        """
        self.ensure_remaining_bytes(4, "read_int32")
        value: int = struct.unpack("<I", self.data[self.offset : self.offset + 4])[0]
        self.offset += 4
        return value

    def read_spell_slot(self, max_slot: int = 35) -> int:
        """Lee un slot de hechizo (byte) y valida su rango.

        Args:
            max_slot: Máximo slot permitido (inclusive).

        Returns:
            Slot leído (1-based).

        Raises:
            ValueError: Si el slot está fuera del rango permitido.
        """
        slot = self.read_byte()
        if not 1 <= slot <= max_slot:
            message = f"Slot de hechizo fuera de rango: {slot}"
            raise ValueError(message)
        return slot

    def read_string(self) -> str:
        """Lee un string del packet.

        El formato es:
        - 2 bytes: longitud del string en bytes (uint16 little-endian)
        - N bytes: string codificado en UTF-16LE

        Returns:
            String decodificado.
        """
        import logging  # noqa: PLC0415

        logger = logging.getLogger(__name__)

        length = self.read_int16()
        self.ensure_remaining_bytes(length, "read_string")
        string_bytes = self.data[self.offset : self.offset + length]

        logger.debug(
            "read_string: length=%d, bytes=%s",
            length,
            string_bytes.hex() if string_bytes else "empty",
        )

        value = string_bytes.decode("utf-16-le")
        self.offset += length

        logger.debug("read_string: decoded='%s'", value)

        return value

    def read_ascii_string(self) -> str:
        """Lee un string ASCII/Latin-1 del packet (cliente Godot).

        El formato es:
        - 2 bytes: longitud del string en bytes (uint16 little-endian)
        - N bytes: string codificado en Latin-1 (soporta caracteres especiales como ñ)

        Returns:
            String decodificado.
        """
        import logging  # noqa: PLC0415

        logger = logging.getLogger(__name__)

        length = self.read_int16()
        self.ensure_remaining_bytes(length, "read_ascii_string")
        string_bytes = self.data[self.offset : self.offset + length]

        logger.debug(
            "read_ascii_string: length=%d, bytes=%s",
            length,
            string_bytes.hex() if string_bytes else "empty",
        )

        value = string_bytes.decode("latin-1")  # Latin-1 soporta caracteres especiales
        self.offset += length

        logger.debug("read_ascii_string: decoded='%s'", value)

        return value

    def remaining_bytes(self) -> int:
        """Retorna el número de bytes restantes sin leer.

        Returns:
            Cantidad de bytes disponibles desde el offset actual.
        """
        return len(self.data) - self.offset

    def has_more_data(self) -> bool:
        """Verifica si quedan bytes por leer.

        Returns:
            True si hay más datos disponibles, False en caso contrario.
        """
        return self.offset < len(self.data)

    def reset(self) -> None:
        """Resetea el offset al inicio (después del PacketID)."""
        self.offset = 1

    def get_packet_id(self) -> int:
        """Retorna el PacketID (primer byte del packet).

        Returns:
            PacketID del packet.
        """
        return self.data[0] if len(self.data) > 0 else 0

    def validate_remaining_bytes(self, required_bytes: int) -> bool:
        """Valida que haya suficientes bytes restantes para leer.

        Args:
            required_bytes: Número de bytes requeridos.

        Returns:
            True si hay suficientes bytes, False en caso contrario.
        """
        return len(self.data) >= self.offset + required_bytes

    def ensure_remaining_bytes(self, required_bytes: int, context: str = "") -> None:
        """Valida que haya suficientes bytes y lanza excepción si no.

        Args:
            required_bytes: Número de bytes requeridos.
            context: Contexto para el mensaje de error (opcional).

        Raises:
            ValueError: Si no hay suficientes bytes restantes.
        """
        if not self.validate_remaining_bytes(required_bytes):
            remaining = len(self.data) - self.offset
            msg = (
                f"Packet truncado: se requieren {required_bytes} bytes pero solo quedan {remaining}"
            )
            if context:
                msg = f"{context}: {msg}"
            raise ValueError(msg)
