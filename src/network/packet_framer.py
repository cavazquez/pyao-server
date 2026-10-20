"""Reconstrucción determinista de paquetes AO según el contrato compartido.

Cada conexión conserva su propia instancia. No se saltean bytes desconocidos ni
se interpreta la frontera TCP como frontera de un mensaje. No realiza I/O.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, ClassVar

CONTRACT: dict[str, Any] = json.loads(
    (Path(__file__).parent / "protocol/contract.json").read_text(encoding="utf-8")
)
WIDTHS = {"u8": 1, "i16": 2, "i32": 4, "u32": 4, "f32": 4}


class FramingError(Exception):
    """Error irrecuperable: cerrar la conexión sin buscar otra frontera."""


class UnknownPacketError(FramingError):
    """ID sin layout soportado en esta dirección."""

    def __init__(self, packet_id: int) -> None:
        """Conserva sólo el ID, nunca los bytes del paquete."""
        super().__init__(f"packet_id desconocido o no soportado: {packet_id}")
        self.packet_id = packet_id


class BufferOverflowError(FramingError):
    """El remanente excede el límite por conexión."""


class InvalidLengthError(FramingError):
    """Longitud anunciada imposible o fuera del límite del campo."""


class InvalidVariantError(FramingError):
    """Subcomando no soportado: su longitud no se puede inferir."""


def _fields_end(data: bytes, fields: list[dict[str, Any]], offset: int) -> int | None:
    """Calcula el fin sólo si están disponibles todos los campos.

    Returns:
        Offset final o None si faltan bytes.

    Raises:
        InvalidLengthError: Ante una longitud fuera del contrato, sin esperar payload.
    """
    for field in fields:
        kind = field["type"]
        if kind == "str16":
            if len(data) < offset + 2:
                return None
            length = int.from_bytes(data[offset : offset + 2], "little")
            offset += 2
            if not field.get("min_bytes", 0) <= length <= field["max_bytes"]:
                msg = "Longitud de cadena fuera del contrato"
                raise InvalidLengthError(msg)
            offset += length
        else:
            offset += WIDTHS[kind]
        if offset > CONTRACT["max_packet_bytes"]:
            msg = "Longitud de paquete fuera del contrato"
            raise InvalidLengthError(msg)
        if offset > len(data):
            return None
    return offset


def packet_length(data: bytes, direction: str = "client") -> int | None:
    """Determina una frontera completa a partir de campos, incluidos subtipos.

    Returns:
        Longitud completa o None si faltan bytes.

    Raises:
        UnknownPacketError: ID sin layout.
        InvalidVariantError: Subtipo/subcomando desconocido.
    """
    if not data:
        return None
    entry = CONTRACT["directions"][direction].get(str(data[0]))
    if entry is None or entry["status"] != "supported":
        raise UnknownPacketError(data[0])
    end = _fields_end(data, entry["fields"], 1)
    if end is None or "variants" not in entry:
        return end
    variant = entry["variants"].get(str(data[1]))
    if variant is None:
        msg = f"Subtipo no soportado para ID {data[0]}"
        raise InvalidVariantError(msg)
    return _fields_end(data, variant, end)


class PacketFramer:
    """Acumula un remanente acotado y extrae mensajes completos en orden."""

    MAX_BUFFER_BYTES: ClassVar[int] = CONTRACT["max_packet_bytes"]

    def __init__(self) -> None:
        """Crea un buffer exclusivo de la conexión."""
        self._buffer = bytearray()

    def feed(self, data: bytes) -> None:
        """Agrega una lectura; el consumidor drena mensajes después de cada feed.

        Raises:
            BufferOverflowError: Si excede el límite sin drenar el remanente.
        """
        if len(self._buffer) + len(data) > self.MAX_BUFFER_BYTES:
            msg = f"Buffer de framing superó {self.MAX_BUFFER_BYTES} bytes"
            raise BufferOverflowError(msg)
        self._buffer.extend(data)

    def next_packet(self) -> bytes | None:
        """Extrae el próximo mensaje, o conserva intacto el prefijo incompleto.

        Returns:
            Bytes del paquete completo, o None mientras está incompleto.
        """
        length = packet_length(bytes(self._buffer))
        if length is None:
            return None
        packet = bytes(self._buffer[:length])
        del self._buffer[:length]
        return packet

    @property
    def buffer_size(self) -> int:
        """Cantidad de bytes pendientes; útil para detectar EOF parcial."""
        return len(self._buffer)
