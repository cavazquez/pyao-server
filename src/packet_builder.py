"""Constructor de paquetes de bytes para el protocolo del servidor."""

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
        """Convierte el paquete a bytes.

        Cada entero en el buffer se convierte directamente a su valor
        de byte correspondiente (0-255).

        Returns:
            Representación en bytes del paquete.
        """
        return bytes(self._data)

    def __len__(self) -> int:
        """Retorna la longitud actual del paquete.

        Returns:
            Número de bytes en el paquete.
        """
        return len(self._data)
