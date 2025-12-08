"""Validador para packets de comandos GM."""

import struct
from typing import TYPE_CHECKING, Any

from src.network.validation_result import ValidationResult

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext

MAP_ID_MAX = 1000
POS_MAX = 100


class GMCommandsPacketValidator:
    """Valida packet GM_COMMANDS completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet GM_COMMANDS.

        Returns:
            ValidationResult con datos GM o error.
        """
        try:
            subcommand = context.reader.read_byte()
            username = context.reader.read_string()
            map_id = context.reader.read_int16()
            x = context.reader.read_byte()
            y = context.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo packet GM_COMMANDS: {e}")
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        # Validaciones simples de rango
        if not (1 <= map_id <= MAP_ID_MAX):
            context.add_error(f"Map ID inválido: {map_id} (debe estar entre 1-1000)")
        if not (1 <= x <= POS_MAX and 1 <= y <= POS_MAX):
            context.add_error(f"Posición inválida: ({x}, {y}) (debe estar entre 1-100)")
        if not username:
            context.add_error(f"Username inválido: '{username}' (longitud: {len(username)})")

        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(
            success=True,
            data={"subcommand": subcommand, "username": username, "map_id": map_id, "x": x, "y": y},
            error_message=None,
        )
