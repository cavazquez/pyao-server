"""Validador de paquetes para centralizar parsing y validación."""

import logging
import struct
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from src.packet_reader import PacketReader

T = TypeVar("T")

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult[T]:
    """Resultado de validación de un packet.

    Attributes:
        success: True si la validación fue exitosa.
        data: Datos validados (solo si success=True).
        error_message: Mensaje de error (solo si success=False).
    """

    success: bool
    data: T | None = None
    error_message: str | None = None

    def log_validation(self, packet_name: str, packet_id: int, client_address: str) -> None:
        """Registra el resultado de la validación en los logs.

        Args:
            packet_name: Nombre del packet (ej: "WALK", "ATTACK").
            packet_id: ID del packet.
            client_address: Dirección del cliente (IP:Puerto).
        """
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


class PacketValidator:
    """Valida y parsea packets usando PacketReader.

    Centraliza la lógica de parsing y validación para evitar duplicación
    en las tasks.

    Example:
        >>> reader = PacketReader(data)
        >>> validator = PacketValidator(reader)
        >>> slot = validator.read_slot(min_slot=1, max_slot=20)
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

    def read_slot(self, min_slot: int = 1, max_slot: int = 20) -> int | None:
        """Lee y valida un slot de inventario/banco.

        Args:
            min_slot: Slot mínimo válido (default: 1).
            max_slot: Slot máximo válido (default: 20).

        Returns:
            Slot válido o None si hay error.
        """
        try:
            slot = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo slot: {e}")
            return None
        else:
            if not min_slot <= slot <= max_slot:
                msg = f"Slot inválido: {slot} (debe estar entre {min_slot}-{max_slot})"
                self.errors.append(msg)
                return None
            return slot

    def read_quantity(self, min_qty: int = 1, max_qty: int = 10000) -> int | None:
        """Lee y valida una cantidad.

        Args:
            min_qty: Cantidad mínima válida (default: 1).
            max_qty: Cantidad máxima válida (default: 10000).

        Returns:
            Cantidad válida o None si hay error.
        """
        try:
            quantity = self.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo cantidad: {e}")
            return None
        else:
            if not min_qty <= quantity <= max_qty:
                msg = f"Cantidad inválida: {quantity} (debe estar entre {min_qty}-{max_qty})"
                self.errors.append(msg)
                return None
            return quantity

    def read_username(self, max_length: int = 20) -> str | None:
        """Lee y valida un nombre de usuario.

        Args:
            max_length: Longitud máxima del username.

        Returns:
            Username válido o None si hay error.
        """
        try:
            username = self.reader.read_string().strip()
        except (ValueError, IndexError, UnicodeDecodeError, struct.error) as e:
            self.errors.append(f"Error leyendo username: {e}")
            return None
        else:
            if not username:
                self.errors.append("Username vacío")
                return None
            if len(username) > max_length:
                msg = f"Username muy largo: {len(username)} (máximo: {max_length})"
                self.errors.append(msg)
                return None
            return username

    def read_coordinates(self, max_x: int = 100, max_y: int = 100) -> tuple[int, int] | None:
        """Lee y valida coordenadas X, Y.

        Args:
            max_x: Coordenada X máxima.
            max_y: Coordenada Y máxima.

        Returns:
            Tupla (x, y) válida o None si hay error.
        """
        try:
            x = self.reader.read_byte()
            y = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo coordenadas: {e}")
            return None
        else:
            if not (1 <= x <= max_x and 1 <= y <= max_y):
                self.errors.append(f"Coordenadas inválidas: ({x}, {y})")
                return None
            return (x, y)

    def read_password(self, min_length: int = 6, max_length: int = 32) -> str | None:
        """Lee y valida una contraseña.

        Args:
            min_length: Longitud mínima de la contraseña.
            max_length: Longitud máxima de la contraseña.

        Returns:
            Contraseña válida o None si hay error.
        """
        try:
            password = self.reader.read_string()
        except (ValueError, IndexError, UnicodeDecodeError, struct.error) as e:
            self.errors.append(f"Error leyendo contraseña: {e}")
            return None
        else:
            if len(password) < min_length:
                msg = f"Contraseña muy corta: {len(password)} (mínimo: {min_length})"
                self.errors.append(msg)
                return None
            if len(password) > max_length:
                msg = f"Contraseña muy larga: {len(password)} (máximo: {max_length})"
                self.errors.append(msg)
                return None
            return password

    def read_spell_slot(self, max_slot: int = 35) -> int | None:
        """Lee y valida un slot de hechizo.

        Args:
            max_slot: Slot máximo válido (default: 35 para spellbook).

        Returns:
            Slot validado o None si es inválido.
        """
        return self.read_slot(min_slot=1, max_slot=max_slot)

    def read_heading(self) -> int | None:
        """Lee y valida una dirección (heading).

        Valores válidos: 1=Norte, 2=Este, 3=Sur, 4=Oeste

        Returns:
            Heading validado (1-4) o None si es inválido.
        """
        MAX_HEADING = 4  # noqa: N806 - Constante local
        try:
            heading = self.reader.read_byte()

            # Validar rango (1-4)
            if heading < 1 or heading > MAX_HEADING:
                self.errors.append(f"Dirección inválida: {heading} (debe ser 1-4)")
                return None
        except struct.error as e:
            self.errors.append(f"Error al leer heading: {e}")
            return None
        else:
            return heading

    def read_string(
        self, min_length: int = 1, max_length: int = 255, encoding: str = "utf-8"
    ) -> str | None:
        """Lee y valida un string con longitud variable.

        Formato: length (int16 LE) + string bytes

        Args:
            min_length: Longitud mínima del string.
            max_length: Longitud máxima del string.
            encoding: Encoding del string (default: utf-8).

        Returns:
            String validado o None si es inválido.
        """
        try:
            # Leer longitud del string
            length = self.reader.read_int16()

            # Validar longitud
            if length < min_length:
                self.errors.append(f"String muy corto (mínimo {min_length} caracteres)")
                return None

            if length > max_length:
                self.errors.append(f"String muy largo (máximo {max_length} caracteres)")
                return None

            # Verificar que hay suficientes bytes
            if len(self.reader.data) < self.reader.offset + length:
                self.errors.append("Datos insuficientes para leer string")
                return None

            # Leer string
            string_bytes = self.reader.data[self.reader.offset : self.reader.offset + length]
            self.reader.offset += length

            # Decodificar y retornar
            return string_bytes.decode(encoding)

        except (ValueError, UnicodeDecodeError) as e:
            self.errors.append(f"Error al decodificar string: {e}")
            return None
        except struct.error as e:
            self.errors.append(f"Error al leer longitud del string: {e}")
            return None

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

    def validate_gm_teleport(self) -> tuple[int, str, int, int, int] | None:
        """Valida packet GM_COMMANDS (teletransporte).

        Formato esperado:
        - Byte: Subcomando GM (ej: WARP_CHAR)
        - String: Username (UTF-16LE con length prefix)
        - Int16: Map ID
        - Byte: X
        - Byte: Y

        Returns:
            Tupla (subcommand, username, map_id, x, y) o None si hay error.
        """
        try:
            subcommand = self.reader.read_byte()
            username = self.reader.read_string()
            map_id = self.reader.read_int16()
            x = self.reader.read_byte()
            y = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo packet GM_COMMANDS: {e}")
            return None

        # Validar rangos
        if map_id < 1 or map_id > 1000:  # noqa: PLR2004
            self.errors.append(f"Map ID inválido: {map_id} (debe estar entre 1-1000)")
            return None

        if not (1 <= x <= 100 and 1 <= y <= 100):  # noqa: PLR2004
            self.errors.append(f"Posición inválida: ({x}, {y}) (debe estar entre 1-100)")
            return None

        if not username or len(username) > 20:  # noqa: PLR2004
            self.errors.append(f"Username inválido: '{username}' (longitud: {len(username)})")
            return None

        return subcommand, username, map_id, x, y

    def get_all_errors(self) -> list[str]:
        """Retorna todos los mensajes de error.

        Returns:
            Lista de mensajes de error.
        """
        return self.errors.copy()

    def clear_errors(self) -> None:
        """Limpia todos los errores acumulados."""
        self.errors.clear()

    # ========== Métodos de Validación Completa de Packets ==========
    # Estos métodos validan un packet completo y retornan ValidationResult
    # con todos los datos parseados listos para usar en las tasks.

    def validate_packet_by_id(self, packet_id: int) -> ValidationResult[dict[str, Any]] | None:
        """Valida un packet según su ID usando el método validate_* correspondiente.

        Args:
            packet_id: ID del packet a validar.

        Returns:
            ValidationResult si hay un validador para este packet_id, None si no existe.
        """
        # Mapeo de packet_id a método de validación
        # Importar aquí para evitar dependencia circular
        from src.packet_id import ClientPacketID  # noqa: PLC0415

        validators: dict[int, object] = {
            ClientPacketID.WALK: self.validate_walk_packet,
            ClientPacketID.ATTACK: self.validate_attack_packet,
            ClientPacketID.LOGIN: self.validate_login_packet,
            ClientPacketID.CAST_SPELL: self.validate_cast_spell_packet,
            ClientPacketID.DROP: self.validate_drop_packet,
            ClientPacketID.PICK_UP: self.validate_pickup_packet,
        }

        validator_method = validators.get(packet_id)
        if validator_method and callable(validator_method):
            return validator_method()  # type: ignore[no-any-return]

        # No hay validador para este packet_id
        return None

    def validate_walk_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet WALK completo.

        Formato esperado:
        - Byte 0: PacketID (WALK = 6)
        - Byte 1: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste)

        Returns:
            ValidationResult con {"heading": int} si es válido.
        """
        heading = self.read_heading()

        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"heading": heading}, error_message=None)

    def validate_attack_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet ATTACK completo.

        Formato esperado:
        - Byte 0: PacketID (ATTACK = 8)
        - Int16: CharIndex del objetivo

        Returns:
            ValidationResult con {"char_index": int} si es válido.
        """
        try:
            char_index = self.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo char_index: {e}")
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        # Validar rango (CharIndex debe ser > 0)
        if char_index <= 0:
            self.errors.append(f"CharIndex inválido: {char_index} (debe ser > 0)")
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"char_index": char_index}, error_message=None)

    def validate_login_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet LOGIN completo.

        Formato esperado:
        - Byte 0: PacketID (LOGIN = 2)
        - String: Username (UTF-8)
        - String: Password (UTF-8)

        Returns:
            ValidationResult con {"username": str, "password": str} si es válido.
        """
        username = self.read_string(min_length=3, max_length=20, encoding="utf-8")
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        password = self.read_string(min_length=6, max_length=32, encoding="utf-8")
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(
            success=True,
            data={"username": username, "password": password},
            error_message=None,
        )

    def validate_cast_spell_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet CAST_SPELL completo.

        Formato esperado:
        - Byte 0: PacketID (CAST_SPELL = 13)
        - Byte: Slot del hechizo (1-35)

        Returns:
            ValidationResult con {"spell_slot": int} si es válido.
        """
        spell_slot = self.read_spell_slot()

        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"spell_slot": spell_slot}, error_message=None)

    def validate_drop_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet DROP completo.

        Formato esperado:
        - Byte 0: PacketID (DROP = 18)
        - Byte: Slot del inventario (1-20)
        - Int16: Cantidad a tirar

        Returns:
            ValidationResult con {"slot": int, "quantity": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=20)
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        quantity = self.read_quantity(min_qty=1, max_qty=10000)
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(
            success=True, data={"slot": slot, "quantity": quantity}, error_message=None
        )

    def validate_pickup_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet PICK_UP completo.

        Formato esperado:
        - Byte 0: PacketID (PICK_UP = 19)

        Returns:
            ValidationResult con {} (sin datos adicionales) si es válido.
        """
        # PICK_UP no tiene parámetros adicionales, solo el PacketID
        # Verificamos que no haya errores previos
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)
