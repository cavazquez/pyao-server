"""Validadores para packets de autenticación."""

import struct
from typing import TYPE_CHECKING, Any

from src.network.validation_result import ValidationResult
from src.network.validators.helpers import ValidationHelpers

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class LoginPacketValidator:
    """Valida packet LOGIN completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet LOGIN.

        Returns:
            ValidationResult con credenciales o error.
        """
        username = ValidationHelpers.read_string(
            context, min_length=3, max_length=20, encoding="utf-8"
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        password = ValidationHelpers.read_string(
            context, min_length=6, max_length=32, encoding="utf-8"
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(
            success=True,
            data={"username": username, "password": password},
            error_message=None,
        )


class CreateAccountPacketValidator:
    """Valida packet CREATE_ACCOUNT completo."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida packet CREATE_ACCOUNT.

        Returns:
            ValidationResult con datos de creación o error.
        """
        username = ValidationHelpers.read_string(
            context, min_length=3, max_length=20, encoding="utf-8"
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        password = ValidationHelpers.read_string(
            context, min_length=6, max_length=32, encoding="utf-8"
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        # Datos del personaje
        try:
            race = context.reader.read_byte()
            _ = context.reader.read_int16()  # Unknown
            gender = context.reader.read_byte()
            job = context.reader.read_byte()
            _ = context.reader.read_byte()  # Unknown
            head = context.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo datos del personaje: {e}")
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        email = ValidationHelpers.read_string(
            context, min_length=1, max_length=100, encoding="utf-8"
        )
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        try:
            home = context.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            context.add_error(f"Error leyendo home: {e}")
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )

        return ValidationResult(
            success=True,
            data={
                "username": username,
                "password": password,
                "email": email,
                "race": race,
                "gender": gender,
                "job": job,
                "head": head,
                "home": home,
            },
            error_message=None,
        )
