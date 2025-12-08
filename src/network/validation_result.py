"""Dataclass para resultados de validación de packets."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult[T]:
    """Resultado de validación de un packet."""

    success: bool
    data: T | None = None
    error_message: str | None = None

    def log_validation(self, packet_name: str, packet_id: int, client_address: str) -> None:
        """Registra en logs el resultado de validación."""
        if self.success:
            logger.debug(
                "[%s] ✓ Packet %s (ID:%d) validado correctamente: %s",
                client_address,
                packet_name,
                packet_id,
                self.data,
            )
        else:
            logger.warning(
                "[%s] ✗ Packet %s (ID:%d) inválido: %s",
                client_address,
                packet_name,
                packet_id,
                self.error_message,
            )
