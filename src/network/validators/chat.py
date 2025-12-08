"""Validador para packets de chat."""

from typing import TYPE_CHECKING, Any

from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class TalkPacketValidator:
    """Valida packet TALK completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet TALK.

        Returns:
            ValidationResult con mensaje o error.
        """
        message = ValidationHelpers.read_string(
            context, min_length=1, max_length=255, encoding="utf-8"
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(success=True, data={"message": message}, error_message=None)
