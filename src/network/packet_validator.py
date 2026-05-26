"""Validador de paquetes para centralizar parsing y validación."""

import logging
import struct
from typing import TYPE_CHECKING, Any

from src.network.packet_reader_mixin import PacketReaderMixin
from src.network.validation_result import ValidationResult
from src.network.validators.base import ValidationContext
from src.network.validators.registry import get_packet_validator_registry

if TYPE_CHECKING:
    from src.network.packet_reader import PacketReader
else:
    PacketReader = object

logger = logging.getLogger(__name__)


class PacketValidator(PacketReaderMixin):
    """Valida y parsea packets usando PacketReader.

    Centraliza la lógica de parsing y validación para evitar duplicación
    en las tareas. Hereda de PacketReaderMixin para métodos de lectura.

    Example:
        >>> reader = PacketReader(data)
        >>> validator = PacketValidator(reader)
        >>> slot = validator.read_slot(min_slot=1, max_slot=config.max_slot)
        >>> if validator.has_errors():
        ...     print(validator.get_error_message())
    """

    def __init__(self, reader: PacketReader) -> None:
        """Inicializa el validador con un PacketReader.

        Args:
            reader: PacketReader con los datos del packet.
        """
        self.reader = reader
        self.errors: list[str] = []

    def has_errors(self) -> bool:
        """Verifica si hubo errores durante la validación.

        Returns:
            True si hay errores, False en caso contrario.
        """
        return len(self.errors) > 0

    def get_error_message(self) -> str:
        """Obtiene mensaje de error concatenado.

        Returns:
            String con todos los errores separados por comas.
        """
        return ", ".join(self.errors)

    def get_all_errors(self) -> list[str]:
        """Retorna todos los mensajes de error.

        Returns:
            Lista de mensajes de error.
        """
        return self.errors.copy()

    def clear_errors(self) -> None:
        """Limpia todos los errores acumulados."""
        self.errors.clear()

    def validate_packet_by_id(self, packet_id: int) -> ValidationResult[dict[str, Any]] | None:
        """Valida un packet según su ID usando el registry de validadores.

        Returns:
            ValidationResult si existe validador, None si no está registrado.
        """
        validator = get_packet_validator_registry().get_validator(packet_id)
        if validator is None:
            return None

        context = ValidationContext(reader=self.reader, errors=self.errors.copy())
        result = validator.validate(context)
        self.errors = context.errors
        return result

    def validate_slot(self, min_slot: int = 1, max_slot: int = 20) -> ValidationResult[int]:
        """Valida un slot de inventario/banco.

        Args:
            min_slot: Slot mínimo válido (default: 1).
            max_slot: Slot máximo válido (default: 20).

        Returns:
            ValidationResult con el slot validado o error descriptivo.
        """
        try:
            slot = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            return ValidationResult(
                success=False, data=None, error_message=f"Error leyendo slot: {e}"
            )

        if not min_slot <= slot <= max_slot:
            return ValidationResult(
                success=False,
                data=None,
                error_message=f"Slot inválido: {slot} (debe estar entre {min_slot}-{max_slot})",
            )

        return ValidationResult(success=True, data=slot, error_message=None)

    def validate_quantity(self, min_qty: int = 1, max_qty: int = 10000) -> ValidationResult[int]:
        """Valida una cantidad.

        Args:
            min_qty: Cantidad mínima válida (default: 1).
            max_qty: Cantidad máxima válida (default: 10000).

        Returns:
            ValidationResult con la cantidad validada o error descriptivo.
        """
        try:
            quantity = self.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            return ValidationResult(
                success=False, data=None, error_message=f"Error leyendo cantidad: {e}"
            )

        if not min_qty <= quantity <= max_qty:
            return ValidationResult(
                success=False,
                data=None,
                error_message=(
                    f"Cantidad inválida: {quantity} (debe estar entre {min_qty}-{max_qty})"
                ),
            )

        return ValidationResult(success=True, data=quantity, error_message=None)

    def validate_coordinates(
        self, max_x: int = 100, max_y: int = 100
    ) -> ValidationResult[tuple[int, int]]:
        """Valida coordenadas X, Y.

        Args:
            max_x: Coordenada X máxima.
            max_y: Coordenada Y máxima.

        Returns:
            ValidationResult con la tupla (x, y) validada o error descriptivo.
        """
        try:
            x = self.reader.read_byte()
            y = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            return ValidationResult(
                success=False, data=None, error_message=f"Error leyendo coordenadas: {e}"
            )

        if not (1 <= x <= max_x and 1 <= y <= max_y):
            return ValidationResult(
                success=False,
                data=None,
                error_message=(
                    f"Coordenadas inválidas: ({x}, {y}) (deben estar entre 1-{max_x}, 1-{max_y})"
                ),
            )

        return ValidationResult(success=True, data=(x, y), error_message=None)

    def validate_slot_and_quantity(
        self, min_slot: int = 1, max_slot: int = 20, min_qty: int = 1, max_qty: int = 10000
    ) -> ValidationResult[tuple[int, int]]:
        """Valida un slot y una cantidad (patrón común en commerce/bank).

        Args:
            min_slot: Slot mínimo válido.
            max_slot: Slot máximo válido.
            min_qty: Cantidad mínima válida.
            max_qty: Cantidad máxima válida.

        Returns:
            ValidationResult con la tupla (slot, quantity) validada o error descriptivo.
        """
        slot_result = self.validate_slot(min_slot, max_slot)
        if not slot_result.success:
            return ValidationResult(
                success=False,
                data=None,
                error_message=slot_result.error_message,
            )

        qty_result = self.validate_quantity(min_qty, max_qty)
        if not qty_result.success:
            return ValidationResult(
                success=False,
                data=None,
                error_message=qty_result.error_message,
            )

        if slot_result.data is None or qty_result.data is None:
            return ValidationResult(
                success=False,
                data=None,
                error_message="Error interno: datos de validación son None",
            )

        return ValidationResult(
            success=True,
            data=(slot_result.data, qty_result.data),
            error_message=None,
        )

    def validate_string(
        self, min_length: int = 1, max_length: int = 255, encoding: str = "utf-16le"
    ) -> ValidationResult[str]:
        """Valida un string del packet.

        Args:
            min_length: Longitud mínima del string.
            max_length: Longitud máxima del string.
            encoding: Codificación del string (default: utf-16le).

        Returns:
            ValidationResult con el string validado o error descriptivo.
        """
        try:
            length_bytes_size = 2
            length_bytes = self.reader.data[
                self.reader.offset : self.reader.offset + length_bytes_size
            ]
            if len(length_bytes) < length_bytes_size:
                return ValidationResult(
                    success=False,
                    data=None,
                    error_message="Error leyendo longitud del string: packet truncado",
                )

            length = struct.unpack("<H", length_bytes)[0]

            if length < min_length or length > max_length:
                return ValidationResult(
                    success=False,
                    data=None,
                    error_message=(
                        f"Longitud de string inválida: {length} "
                        f"(debe estar entre {min_length}-{max_length})"
                    ),
                )

            self.reader.offset += 2
            string_bytes = self.reader.data[self.reader.offset : self.reader.offset + length]

            if len(string_bytes) < length:
                return ValidationResult(
                    success=False,
                    data=None,
                    error_message=(
                        f"String truncado: se esperaban {length} bytes, hay {len(string_bytes)}"
                    ),
                )

            string_value = string_bytes.decode(encoding)
            self.reader.offset += length

        except (ValueError, IndexError, struct.error, UnicodeDecodeError) as e:
            return ValidationResult(
                success=False, data=None, error_message=f"Error leyendo string: {e}"
            )

        if not string_value:
            return ValidationResult(success=False, data=None, error_message="String vacío")

        return ValidationResult(success=True, data=string_value, error_message=None)
