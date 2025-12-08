"""Helpers estáticos para lectura y validación de datos de packets."""

import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class ValidationHelpers:
    """Métodos helper para validación de campos comunes."""

    @staticmethod
    def read_slot(context: ValidationContext, min_slot: int = 1, max_slot: int = 20) -> int | None:
        """Lee y valida un slot.

        Returns:
            Slot válido o None si hay error.
        """
        try:
            slot = context.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo slot: {e}")
            return None

        if not min_slot <= slot <= max_slot:
            context.add_error(f"Slot inválido: {slot} (debe estar entre {min_slot}-{max_slot})")
            return None
        return slot

    @staticmethod
    def read_quantity(
        context: ValidationContext, min_qty: int = 1, max_qty: int = 10000
    ) -> int | None:
        """Lee y valida una cantidad.

        Returns:
            Cantidad válida o None si hay error.
        """
        try:
            quantity = context.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo cantidad: {e}")
            return None

        if not min_qty <= quantity <= max_qty:
            context.add_error(
                f"Cantidad inválida: {quantity} (debe estar entre {min_qty}-{max_qty})"
            )
            return None
        return quantity

    @staticmethod
    def read_gold_amount(
        context: ValidationContext,
        min_amount: int = 0,
        max_amount: int = 999_999_999,
    ) -> int | None:
        """Lee y valida una cantidad de oro.

        Returns:
            Cantidad válida o None si hay error.
        """
        try:
            amount = context.reader.read_int32()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo cantidad de oro: {e}")
            return None

        if not min_amount <= amount <= max_amount:
            context.add_error(
                f"Cantidad de oro inválida: {amount} (debe estar entre {min_amount}-{max_amount})"
            )
            return None
        return amount

    @staticmethod
    def read_username(context: ValidationContext, max_length: int = 20) -> str | None:
        """Lee y valida un username.

        Returns:
            Username válido o None si hay error.
        """
        try:
            username = context.reader.read_string().strip()
        except (ValueError, IndexError, UnicodeDecodeError, struct.error) as e:
            context.add_error(f"Error leyendo username: {e}")
            return None

        if not username:
            context.add_error("Username vacío")
            return None
        if len(username) > max_length:
            context.add_error(f"Username muy largo: {len(username)} (máximo: {max_length})")
            return None
        return username

    @staticmethod
    def read_password(
        context: ValidationContext, min_length: int = 6, max_length: int = 32
    ) -> str | None:
        """Lee y valida un password.

        Returns:
            Password válido o None si hay error.
        """
        try:
            password = context.reader.read_string().strip()
        except (ValueError, IndexError, UnicodeDecodeError, struct.error) as e:
            context.add_error(f"Error leyendo password: {e}")
            return None

        if len(password) < min_length:
            context.add_error(f"Password muy corta (mínimo {min_length} caracteres)")
            return None
        if len(password) > max_length:
            context.add_error(f"Password muy larga (máximo {max_length} caracteres)")
            return None
        return password

    @staticmethod
    def read_coordinates(
        context: ValidationContext, max_x: int = 100, max_y: int = 100
    ) -> tuple[int, int] | None:
        """Lee y valida coordenadas.

        Returns:
            Tupla (x, y) válida o None si hay error.
        """
        try:
            x = context.reader.read_byte()
            y = context.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo coordenadas: {e}")
            return None

        if not (1 <= x <= max_x and 1 <= y <= max_y):
            context.add_error(f"Coordenadas inválidas: ({x}, {y})")
            return None
        return (x, y)

    @staticmethod
    def read_heading(context: ValidationContext) -> int | None:
        """Lee y valida heading (1-4).

        Returns:
            Heading válido o None si hay error.
        """
        max_heading = 4
        try:
            heading = context.reader.read_byte()
        except struct.error as e:
            context.add_error(f"Error al leer heading: {e}")
            return None

        if heading < 1 or heading > max_heading:
            context.add_error(f"Dirección inválida: {heading} (debe ser 1-4)")
            return None
        return heading

    @staticmethod
    def read_spell_slot(context: ValidationContext, max_slot: int = 35) -> int | None:
        """Lee y valida un slot de hechizo.

        Returns:
            Slot válido o None si hay error.
        """
        return ValidationHelpers.read_slot(context, min_slot=1, max_slot=max_slot)

    @staticmethod
    def read_string(
        context: ValidationContext,
        min_length: int = 1,
        max_length: int = 255,
        encoding: str = "utf-8",
    ) -> str | None:
        """Lee y valida un string con longitud variable.

        Returns:
            String válido o None si hay error.
        """
        try:
            length = context.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error al leer longitud del string: {e}")
            return None

        if length < min_length:
            context.add_error(f"String muy corto (mínimo {min_length} caracteres)")
            return None
        if length > max_length:
            context.add_error(f"String muy largo (máximo {max_length} caracteres)")
            return None

        if len(context.reader.data) < context.reader.offset + length:
            context.add_error("Datos insuficientes para leer string")
            return None

        try:
            string_bytes = context.reader.data[
                context.reader.offset : context.reader.offset + length
            ]
            context.reader.offset += length
            return string_bytes.decode(encoding, errors="strict")
        except (UnicodeDecodeError, ValueError) as e:
            context.add_error(f"Error al decodificar string: {e}")
            return None
