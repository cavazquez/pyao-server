"""Validadores para packets de inventario."""

from typing import TYPE_CHECKING, Any

from src.config.config_manager import ConfigManager, config_manager
from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class DropPacketValidator:
    """Valida packet DROP completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet DROP.

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


class PickupPacketValidator:
    """Valida packet PICK_UP completo (sin parámetros)."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet PICK_UP.

        Returns:
            ValidationResult vacío o error.
        """
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)


class EquipItemPacketValidator:
    """Valida packet EQUIP_ITEM completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet EQUIP_ITEM.

        Returns:
            ValidationResult con slot o error.
        """
        slot = ValidationHelpers.read_slot(
            context,
            min_slot=1,
            max_slot=ConfigManager.as_int(config_manager.get("game.max_inventory_slots", 25)),
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"slot": slot}, error_message=None)


class UseItemPacketValidator:
    """Valida packet USE_ITEM completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet USE_ITEM.

        Returns:
            ValidationResult con slot o error.
        """
        slot = ValidationHelpers.read_slot(
            context,
            min_slot=1,
            max_slot=ConfigManager.as_int(config_manager.get("game.max_inventory_slots", 25)),
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"slot": slot}, error_message=None)


class DoubleClickPacketValidator:
    """Valida packet DOUBLE_CLICK completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet DOUBLE_CLICK.

        Returns:
            ValidationResult con slot o error.
        """
        slot = ValidationHelpers.read_slot(context, min_slot=0, max_slot=255)
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={"slot": slot}, error_message=None)


class LeftClickPacketValidator:
    """Valida packet LEFT_CLICK completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet LEFT_CLICK.

        Returns:
            ValidationResult con coordenadas o error.
        """
        coords = ValidationHelpers.read_coordinates(context, max_x=100, max_y=100)
        if context.has_errors() or coords is None:
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(
            success=True, data={"x": coords[0], "y": coords[1]}, error_message=None
        )
