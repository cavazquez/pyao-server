"""Validadores para packets de movimiento."""

from typing import TYPE_CHECKING, Any

from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class WalkPacketValidator:
    """Valida packet WALK completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet WALK.

        Returns:
            ValidationResult con heading o error.
        """
        heading = ValidationHelpers.read_heading(context)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"heading": heading}, error_message=None)


class AttackPacketValidator:
    """Valida packet ATTACK completo (sin parámetros)."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet ATTACK.

        Returns:
            ValidationResult vacío o error.
        """
        _ = context  # no params
        return ValidationResult(success=True, data={}, error_message=None)


class ChangeHeadingPacketValidator:
    """Valida packet CHANGE_HEADING completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet CHANGE_HEADING.

        Returns:
            ValidationResult con heading o error.
        """
        heading = ValidationHelpers.read_heading(context)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"heading": heading}, error_message=None)


class RequestPositionUpdatePacketValidator:
    """Valida packet REQUEST_POSITION_UPDATE completo (sin parámetros)."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_POSITION_UPDATE.

        Returns:
            ValidationResult vacío o error.
        """
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)
