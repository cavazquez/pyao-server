"""Validadores para packets de comercio."""

from typing import TYPE_CHECKING, Any

from src.config.config_manager import ConfigManager, config_manager
from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class CommerceBuyPacketValidator:
    """Valida packet COMMERCE_BUY completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida compra a mercader.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        slot = ValidationHelpers.read_slot(context, min_slot=1, max_slot=50)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        quantity = ValidationHelpers.read_quantity(context, min_qty=1, max_qty=10000)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(
            success=True, data={"slot": slot, "quantity": quantity}, error_message=None
        )


class CommerceSellPacketValidator:
    """Valida packet COMMERCE_SELL completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida venta al mercader.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        slot = ValidationHelpers.read_slot(
            context,
            min_slot=1,
            max_slot=ConfigManager.as_int(config_manager.get("game.inventory.max_slots", 30)),
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        quantity = ValidationHelpers.read_quantity(context, min_qty=1, max_qty=10000)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(
            success=True, data={"slot": slot, "quantity": quantity}, error_message=None
        )


class CommerceEndPacketValidator:
    """Valida packet COMMERCE_END completo (sin parámetros)."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida cierre de comercio (sin parámetros).

        Returns:
            ValidationResult vacío o error.
        """
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)
