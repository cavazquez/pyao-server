"""Validadores para packets simples (sin parámetros)."""

from typing import TYPE_CHECKING, Any

from src.network.validation_result import ValidationResult

if TYPE_CHECKING:
    from src.network.validators.base import ValidationContext


class SimplePacketValidator:
    """Validador genérico para packets sin parámetros."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida un packet sin parámetros.

        Returns:
            ValidationResult vacío o error.
        """
        if context.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=context.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)


# Instancias específicas
class ThrowDicesPacketValidator(SimplePacketValidator):
    """Valida packet THROW_DICES."""


class RequestAttributesPacketValidator(SimplePacketValidator):
    """Valida packet REQUEST_ATTRIBUTES."""


class MeditatePacketValidator(SimplePacketValidator):
    """Valida packet MEDITATE."""


class RequestStatsPacketValidator(SimplePacketValidator):
    """Valida packet REQUEST_STATS."""


class InformationPacketValidator(SimplePacketValidator):
    """Valida packet INFORMATION."""


class RequestMotdPacketValidator(SimplePacketValidator):
    """Valida packet REQUEST_MOTD."""


class UptimePacketValidator(SimplePacketValidator):
    """Valida packet UPTIME."""


class OnlinePacketValidator(SimplePacketValidator):
    """Valida packet ONLINE."""


class QuitPacketValidator(SimplePacketValidator):
    """Valida packet QUIT."""


class PingPacketValidator(SimplePacketValidator):
    """Valida packet PING."""


class AyudaPacketValidator(SimplePacketValidator):
    """Valida packet AYUDA."""
