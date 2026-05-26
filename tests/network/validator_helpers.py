"""Helpers para tests de PacketValidator."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.network.packet_id import ClientPacketID
    from src.network.packet_validator import PacketValidator
    from src.network.validation_result import ValidationResult


def validate_registered_packet(
    validator: PacketValidator, packet_id: ClientPacketID
) -> ValidationResult:
    """Valida un packet registrado; falla el test si no hay validador."""
    result = validator.validate_packet_by_id(int(packet_id))
    assert result is not None, f"No hay validador registrado para {packet_id!r}"
    return result
