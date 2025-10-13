"""Constructor de paquetes de bytes para el protocolo del servidor.

Ejemplo de uso:
    >>> packet = PacketBuilder()
    >>> packet.add_byte(1).add_int16(1000).add_int32(100000)
    >>> data = packet.to_bytes()
"""

# Constantes para validación de bytes
MAX_BYTE_VALUE = 255
MIN_BYTE_VALUE = 0


class PacketBuilder:
    """Construye paquetes de bytes de forma incremental."""

    def __init__(self) -> None:
        """Inicializa un nuevo constructor de paquetes."""
        self._data: list[int] = []

    def add_byte(self, value: int) -> PacketBuilder:
        """Agrega un byte al paquete.

        Args:
            value: Valor del byte (0-255).

        Returns:
            Self para permitir encadenamiento de métodos.

        Raises:
            ValueError: Si value no está en el rango 0-255.
        """
        if not MIN_BYTE_VALUE <= value <= MAX_BYTE_VALUE:
            msg = f"Byte value must be in range {MIN_BYTE_VALUE}-{MAX_BYTE_VALUE}, got {value}"
            raise ValueError(msg)
        self._data.append(value)
        return self

    def add_int16(self, value: int) -> PacketBuilder:
        """Agrega un entero de 16 bits en little-endian.

        Args:
            value: Valor del entero (-32768 a 32767 para signed, 0 a 65535 para unsigned).

        Returns:
            Self para permitir encadenamiento de métodos.
        """
        # Convertir a bytes en little-endian (2 bytes)
        self._data.extend(value.to_bytes(2, byteorder="little", signed=True))
        return self

    def add_int32(self, value: int) -> PacketBuilder:
        """Agrega un entero de 32 bits en little-endian.

        Args:
            value: Valor del entero (-2147483648 a 2147483647 para signed).

        Returns:
            Self para permitir encadenamiento de métodos.
        """
        # Convertir a bytes en little-endian (4 bytes)
        self._data.extend(value.to_bytes(4, byteorder="little", signed=True))
        return self

    def add_string(self, text: str, encoding: str = "utf-8") -> PacketBuilder:
        """Agrega una cadena de texto al paquete.

        Args:
            text: Texto a agregar.
            encoding: Codificación a usar (default: utf-8).

        Returns:
            Self para permitir encadenamiento de métodos.
        """
        encoded = text.encode(encoding)
        self._data.extend(encoded)
        return self

    def add_bytes(self, data: bytes) -> PacketBuilder:
        """Agrega bytes directamente al paquete.

        Args:
            data: Bytes a agregar.

        Returns:
            Self para permitir encadenamiento de métodos.
        """
        self._data.extend(data)
        return self

    def to_bytes(self) -> bytes:
        """Convierte el paquete a bytes con prefijo de longitud.

        El protocolo AO requiere que cada paquete tenga un prefijo de longitud (int16)
        antes del contenido. La longitud incluye el tamaño del paquete completo
        (longitud + contenido).

        Returns:
            Representación en bytes del paquete con prefijo de longitud.
        """
        # Calcular longitud total: 2 bytes (int16 de longitud) + contenido
        packet_length = len(self._data) + 2

        # Crear el paquete final: [longitud_int16][contenido]
        length_bytes = packet_length.to_bytes(2, byteorder="little", signed=True)
        return length_bytes + bytes(self._data)

    def __len__(self) -> int:
        """Retorna la longitud actual del paquete.

        Returns:
            Número de bytes en el paquete.
        """
        return len(self._data)
