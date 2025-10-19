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
            
        Raises:
            struct.error: Si no hay suficientes bytes disponibles.
        """
        value = struct.unpack("B", self.data[self.offset : self.offset + 1])[0]
        self.offset += 1
        return value

    def read_int16(self) -> int:
        """Lee un int16 little-endian (2 bytes).
        
        Returns:
            Valor entero sin signo (0-65535).
            
        Raises:
            struct.error: Si no hay suficientes bytes disponibles.
        """
        value = struct.unpack("<H", self.data[self.offset : self.offset + 2])[0]
        self.offset += 2
        return value

    def read_int32(self) -> int:
        """Lee un int32 little-endian (4 bytes).
        
        Returns:
            Valor entero sin signo (0-4294967295).
            
        Raises:
            struct.error: Si no hay suficientes bytes disponibles.
        """
        value = struct.unpack("<I", self.data[self.offset : self.offset + 4])[0]
        self.offset += 4
        return value

    def read_string(self) -> str:
        """Lee un string: length (uint16 LE) + UTF-16LE bytes.
        
        El formato es:
        - 2 bytes: longitud del string en bytes (uint16 little-endian)
        - N bytes: string codificado en UTF-16LE
        
        Returns:
            String decodificado.
            
        Raises:
            struct.error: Si no hay suficientes bytes para la longitud.
            UnicodeDecodeError: Si los bytes no son UTF-16LE válido.
        """
        length = self.read_int16()
        value = self.data[self.offset : self.offset + length].decode("utf-16-le")
        self.offset += length
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
