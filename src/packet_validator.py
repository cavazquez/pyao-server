"""Validador de paquetes para centralizar parsing y validación."""

import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, TypeVar

if TYPE_CHECKING:
    from src.packet_reader import PacketReader

T = TypeVar("T")


@dataclass
class ValidationResult[T]:
    """Resultado de validación de un packet.

    Attributes:
        success: True si la validación fue exitosa.
        data: Datos validados (solo si success=True).
        error_message: Mensaje de error (solo si success=False).
    """

    success: bool
    data: T | None = None
    error_message: str | None = None


class PacketValidator:
    """Valida y parsea packets usando PacketReader.

    Centraliza la lógica de parsing y validación para evitar duplicación
    en las tasks.

    Example:
        >>> reader = PacketReader(data)
        >>> validator = PacketValidator(reader)
        >>> slot = validator.read_slot(min_slot=1, max_slot=20)
        >>> if validator.has_errors():
        ...     print(validator.get_error_message())
    """

    def __init__(self, reader: PacketReader) -> None:
        """Inicializa el validador con un PacketReader.

        Args:
            reader: PacketReader con los datos del packet.
        """
        self.reader = reader
        self.errors: list[str] = []

    def read_slot(self, min_slot: int = 1, max_slot: int = 20) -> int | None:
        """Lee y valida un slot de inventario/banco.

        Args:
            min_slot: Slot mínimo válido (default: 1).
            max_slot: Slot máximo válido (default: 20).

        Returns:
            Slot válido o None si hay error.
        """
        try:
            slot = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo slot: {e}")
            return None
        else:
            if not min_slot <= slot <= max_slot:
                msg = f"Slot inválido: {slot} (debe estar entre {min_slot}-{max_slot})"
                self.errors.append(msg)
                return None
            return slot

    def read_quantity(self, min_qty: int = 1, max_qty: int = 10000) -> int | None:
        """Lee y valida una cantidad.

        Args:
            min_qty: Cantidad mínima válida (default: 1).
            max_qty: Cantidad máxima válida (default: 10000).

        Returns:
            Cantidad válida o None si hay error.
        """
        try:
            quantity = self.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo cantidad: {e}")
            return None
        else:
            if not min_qty <= quantity <= max_qty:
                msg = f"Cantidad inválida: {quantity} (debe estar entre {min_qty}-{max_qty})"
                self.errors.append(msg)
                return None
            return quantity

    def read_username(self, max_length: int = 20) -> str | None:
        """Lee y valida un nombre de usuario.

        Args:
            max_length: Longitud máxima del username.

        Returns:
            Username válido o None si hay error.
        """
        try:
            username = self.reader.read_string().strip()
        except (ValueError, IndexError, UnicodeDecodeError, struct.error) as e:
            self.errors.append(f"Error leyendo username: {e}")
            return None
        else:
            if not username:
                self.errors.append("Username vacío")
                return None
            if len(username) > max_length:
                msg = f"Username muy largo: {len(username)} (máximo: {max_length})"
                self.errors.append(msg)
                return None
            return username

    def read_coordinates(self, max_x: int = 100, max_y: int = 100) -> tuple[int, int] | None:
        """Lee y valida coordenadas X, Y.

        Args:
            max_x: Coordenada X máxima.
            max_y: Coordenada Y máxima.

        Returns:
            Tupla (x, y) válida o None si hay error.
        """
        try:
            x = self.reader.read_byte()
            y = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo coordenadas: {e}")
            return None
        else:
            if not (1 <= x <= max_x and 1 <= y <= max_y):
                self.errors.append(f"Coordenadas inválidas: ({x}, {y})")
                return None
            return (x, y)

    def read_password(self, min_length: int = 6, max_length: int = 32) -> str | None:
        """Lee y valida una contraseña.

        Args:
            min_length: Longitud mínima de la contraseña.
            max_length: Longitud máxima de la contraseña.

        Returns:
            Contraseña válida o None si hay error.
        """
        try:
            password = self.reader.read_string()
        except (ValueError, IndexError, UnicodeDecodeError, struct.error) as e:
            self.errors.append(f"Error leyendo contraseña: {e}")
            return None
        else:
            if len(password) < min_length:
                msg = f"Contraseña muy corta: {len(password)} (mínimo: {min_length})"
                self.errors.append(msg)
                return None
            if len(password) > max_length:
                msg = f"Contraseña muy larga: {len(password)} (máximo: {max_length})"
                self.errors.append(msg)
                return None
            return password

    def read_spell_slot(self, max_slot: int = 35) -> int | None:
        """Lee y valida un slot de hechizo.

        Args:
            max_slot: Slot máximo válido para hechizos (default: 35).

        Returns:
            Slot de hechizo válido o None si hay error.
        """
        return self.read_slot(min_slot=1, max_slot=max_slot)

    def has_errors(self) -> bool:
        """Verifica si hubo errores durante la validación.

        Returns:
            True si hay errores, False en caso contrario.
        """
        return len(self.errors) > 0

    def get_error_message(self) -> str:
        """Retorna el primer mensaje de error o un mensaje genérico.

        Returns:
            Mensaje de error descriptivo.
        """
        return self.errors[0] if self.errors else "Error desconocido"

    def get_all_errors(self) -> list[str]:
        """Retorna todos los mensajes de error.

        Returns:
            Lista de mensajes de error.
        """
        return self.errors.copy()

    def clear_errors(self) -> None:
        """Limpia todos los errores acumulados."""
        self.errors.clear()
