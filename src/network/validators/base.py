"""Base classes y protocolos para validadores de packets."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from src.network.packet_reader import PacketReader
    from src.network.validation_result import ValidationResult


@dataclass
class ValidationContext:
    """Contexto compartido para validación de packets."""

    reader: PacketReader
    errors: list[str]

    def add_error(self, message: str) -> None:
        """Agrega un error al contexto."""
        self.errors.append(message)

    def has_errors(self) -> bool:
        """Indica si existen errores acumulados.

        Returns:
            True si hay errores, False si no.
        """
        return len(self.errors) > 0

    def get_error_message(self) -> str:
        """Concatena todos los errores en un solo string.

        Returns:
            Cadena con los errores separados por coma.
        """
        return ", ".join(self.errors)


class PacketValidatorProtocol(Protocol):
    """Protocolo que deben implementar todos los validadores."""

    def validate(self, context: ValidationContext) -> ValidationResult[dict[str, Any]]:
        """Valida un packet completo y devuelve ValidationResult."""
        ...
