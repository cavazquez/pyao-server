"""Validadores para packets de hechizos."""

import struct
from typing import TYPE_CHECKING, Any

from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class CastSpellPacketValidator:
    """Valida packet CAST_SPELL completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet CAST_SPELL.

        Returns:
            ValidationResult con {"spell_slot": int} o error.
        """
        spell_slot = ValidationHelpers.read_spell_slot(context)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(success=True, data={"spell_slot": spell_slot}, error_message=None)


class SpellInfoPacketValidator:
    """Valida packet SPELL_INFO completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet SPELL_INFO.

        Returns:
            ValidationResult con {"slot": int} o error.
        """
        slot = ValidationHelpers.read_spell_slot(context, max_slot=35)
        if context.has_errors() or slot is None:
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"slot": slot}, error_message=None)


class MoveSpellPacketValidator:
    """Valida el packet MOVE_SPELL."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet MOVE_SPELL y devuelve slot y dirección.

        Returns:
            ValidationResult con {"slot": int, "upwards": bool} o error.
        """
        try:
            upwards_flag = context.reader.read_byte()
            slot = ValidationHelpers.read_spell_slot(context, max_slot=35)
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo MoveSpell: {e}")
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        upwards = upwards_flag != 0

        if context.has_errors() or slot is None:
            error_message = context.get_error_message() or "Movimiento de hechizo inválido"
            return ValidationResult(success=False, data=None, error_message=error_message)

        return ValidationResult(
            success=True,
            data={"slot": slot, "upwards": upwards},
            error_message=None,
        )
