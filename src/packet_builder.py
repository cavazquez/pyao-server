"""Constructor de paquetes de bytes para el protocolo del servidor."""


class PacketBuilder:
    """Construye paquetes de bytes de forma incremental."""

    def __init__(self) -> None:
        """Inicializa un nuevo constructor de paquetes."""
        self._data: list[int] = []

    def add_byte(self, value: int) -> "PacketBuilder":
        """Agrega un byte al paquete.

        Args:
            value: Valor del byte (0-255).

        Returns:
            Self para permitir encadenamiento de métodos.
        """
        self._data.append(value)
        return self

    def to_bytes(self) -> bytes:
        """Convierte el paquete a bytes.

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
