"""Validadores para packets de banco."""

from typing import TYPE_CHECKING, Any

from src.config.config_manager import ConfigManager, config_manager
from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class BankDepositPacketValidator:
    """Valida packet BANK_DEPOSIT completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida depósito de ítems en banco.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        slot = ValidationHelpers.read_slot(context, min_slot=1, max_slot=20)
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


class BankExtractItemPacketValidator:
    """Valida packet BANK_EXTRACT_ITEM completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida extracción de ítems del banco.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        slot = ValidationHelpers.read_slot(
            context,
            min_slot=1,
            max_slot=ConfigManager.as_int(config_manager.get("game.bank.max_slots", 40)),
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


class BankExtractGoldPacketValidator:
    """Valida packet BANK_EXTRACT_GOLD completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida extracción de oro del banco.

        Returns:
            ValidationResult con amount o error.
        """
        amount = ValidationHelpers.read_gold_amount(context, min_amount=0, max_amount=999_999_999)
        if context.has_errors() or amount is None:
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"amount": amount}, error_message=None)


class BankDepositGoldPacketValidator:
    """Valida packet BANK_DEPOSIT_GOLD completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida depósito de oro en banco.

        Returns:
            ValidationResult con amount o error.
        """
        amount = ValidationHelpers.read_gold_amount(context, min_amount=0, max_amount=999_999_999)
        if context.has_errors() or amount is None:
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"amount": amount}, error_message=None)


class BankEndPacketValidator:
    """Valida packet BANK_END completo (sin parámetros)."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida cierre de sesión de banco (sin parámetros).

        Returns:
            ValidationResult vacío o error.
        """
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)
