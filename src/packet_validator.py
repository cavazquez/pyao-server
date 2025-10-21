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


class PacketValidator:  # noqa: PLR0904 - Muchos métodos validate_* es esperado
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

    def read_gold_amount(self, min_amount: int = 0, max_amount: int = 999999999) -> int | None:
        """Lee y valida una cantidad de oro (int32).

        Args:
            min_amount: Cantidad mínima válida (default: 0).
            max_amount: Cantidad máxima válida (default: 999999999).

        Returns:
            Cantidad de oro válida o None si hay error.
        """
        try:
            amount = self.reader.read_int32()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo cantidad de oro: {e}")
            return None
        else:
            if not min_amount <= amount <= max_amount:
                msg = (
                    f"Cantidad de oro inválida: {amount} "
                    f"(debe estar entre {min_amount}-{max_amount})"
                )
                self.errors.append(msg)
                return None
            return amount

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
            ClientPacketID.LOGIN: self.validate_login_packet,
            ClientPacketID.THROW_DICES: self.validate_throw_dices_packet,
            ClientPacketID.CREATE_ACCOUNT: self.validate_create_account_packet,
            ClientPacketID.TALK: self.validate_talk_packet,
            ClientPacketID.WALK: self.validate_walk_packet,
            ClientPacketID.REQUEST_POSITION_UPDATE: self.validate_request_position_update_packet,
            ClientPacketID.ATTACK: self.validate_attack_packet,
            ClientPacketID.PICK_UP: self.validate_pickup_packet,
            ClientPacketID.REQUEST_ATTRIBUTES: self.validate_request_attributes_packet,
            ClientPacketID.COMMERCE_END: self.validate_commerce_end_packet,
            ClientPacketID.BANK_END: self.validate_bank_end_packet,
            ClientPacketID.DROP: self.validate_drop_packet,
            ClientPacketID.CAST_SPELL: self.validate_cast_spell_packet,
            ClientPacketID.LEFT_CLICK: self.validate_left_click_packet,
            ClientPacketID.DOUBLE_CLICK: self.validate_double_click_packet,
            ClientPacketID.USE_ITEM: self.validate_use_item_packet,
            ClientPacketID.EQUIP_ITEM: self.validate_equip_item_packet,
            ClientPacketID.CHANGE_HEADING: self.validate_change_heading_packet,
            ClientPacketID.COMMERCE_BUY: self.validate_commerce_buy_packet,
            ClientPacketID.BANK_EXTRACT_ITEM: self.validate_bank_extract_packet,
            ClientPacketID.COMMERCE_SELL: self.validate_commerce_sell_packet,
            ClientPacketID.BANK_DEPOSIT: self.validate_bank_deposit_packet,
            ClientPacketID.ONLINE: self.validate_online_packet,
            ClientPacketID.QUIT: self.validate_quit_packet,
            ClientPacketID.MEDITATE: self.validate_meditate_packet,
            ClientPacketID.AYUDA: self.validate_ayuda_packet,
            ClientPacketID.REQUEST_STATS: self.validate_request_stats_packet,
            ClientPacketID.INFORMATION: self.validate_information_packet,
            ClientPacketID.REQUEST_MOTD: self.validate_request_motd_packet,
            ClientPacketID.UPTIME: self.validate_uptime_packet,
            ClientPacketID.PING: self.validate_ping_packet,
            ClientPacketID.BANK_EXTRACT_GOLD: self.validate_bank_extract_gold_packet,
            ClientPacketID.BANK_DEPOSIT_GOLD: self.validate_bank_deposit_gold_packet,
            ClientPacketID.GM_COMMANDS: self.validate_gm_commands_packet,
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

    def validate_attack_packet(self) -> ValidationResult[dict[str, Any]]:  # noqa: PLR6301
        """Valida packet ATTACK completo.

        Formato esperado:
        - Byte 0: PacketID (ATTACK = 8)

        Nota: El packet ATTACK NO tiene parámetros. El jugador ataca en la dirección
        que está mirando (según su heading).

        Returns:
            ValidationResult con dict vacío (packet válido solo con PacketID).
        """
        # El packet ATTACK no tiene datos adicionales, solo el PacketID
        # El jugador ataca en la dirección que está mirando
        return ValidationResult(success=True, data={}, error_message=None)

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

    def validate_talk_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet TALK completo.

        Formato esperado:
        - Byte 0: PacketID (TALK = 3)
        - String: Mensaje (UTF-8)

        Returns:
            ValidationResult con {"message": str} si es válido.
        """
        message = self.read_string(min_length=1, max_length=255, encoding="utf-8")
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"message": message}, error_message=None)

    def validate_double_click_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet DOUBLE_CLICK completo.

        Formato esperado:
        - Byte 0: PacketID (DOUBLE_CLICK = 27)
        - Byte: Slot del inventario (1-20)

        Returns:
            ValidationResult con {"slot": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=20)
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"slot": slot}, error_message=None)

    def validate_left_click_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet LEFT_CLICK completo.

        Formato esperado:
        - Byte 0: PacketID (LEFT_CLICK = 26)
        - Byte: X
        - Byte: Y

        Returns:
            ValidationResult con {"x": int, "y": int} si es válido.
        """
        coords = self.read_coordinates(max_x=100, max_y=100)
        if self.has_errors() or coords is None:
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(
            success=True, data={"x": coords[0], "y": coords[1]}, error_message=None
        )

    def validate_equip_item_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet EQUIP_ITEM completo.

        Formato esperado:
        - Byte 0: PacketID (EQUIP_ITEM = 36)
        - Byte: Slot del inventario (1-20)

        Returns:
            ValidationResult con {"slot": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=20)
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"slot": slot}, error_message=None)

    def validate_use_item_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet USE_ITEM completo.

        Formato esperado:
        - Byte 0: PacketID (USE_ITEM = 30)
        - Byte: Slot del inventario (1-20)

        Returns:
            ValidationResult con {"slot": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=20)
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"slot": slot}, error_message=None)

    def validate_commerce_buy_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet COMMERCE_BUY completo.

        Formato esperado:
        - Byte 0: PacketID (COMMERCE_BUY = 40)
        - Byte: Slot del mercader
        - Int16: Cantidad

        Returns:
            ValidationResult con {"slot": int, "quantity": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=50)  # Mercaderes tienen más slots
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

    def validate_commerce_sell_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet COMMERCE_SELL completo.

        Formato esperado:
        - Byte 0: PacketID (COMMERCE_SELL = 42)
        - Byte: Slot del inventario (1-20)
        - Int16: Cantidad

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

    def validate_bank_deposit_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_DEPOSIT completo.

        Formato esperado:
        - Byte 0: PacketID (BANK_DEPOSIT = 43)
        - Byte: Slot del inventario (1-20)
        - Int16: Cantidad

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

    def validate_bank_extract_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_EXTRACT_ITEM completo.

        Formato esperado:
        - Byte 0: PacketID (BANK_EXTRACT_ITEM = 41)
        - Byte: Slot del banco (1-40)
        - Int16: Cantidad

        Returns:
            ValidationResult con {"slot": int, "quantity": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=40)  # Banco tiene 40 slots
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

    def validate_bank_extract_gold_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_EXTRACT_GOLD completo.

        Formato esperado:
        - Byte 0: PacketID (BANK_EXTRACT_GOLD = 111)
        - Int32: Cantidad de oro a retirar

        Returns:
            ValidationResult con {"amount": int} si es válido.
        """
        amount = self.read_gold_amount(min_amount=0, max_amount=999999999)

        if self.has_errors() or amount is None:
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"amount": amount}, error_message=None)

    def validate_bank_deposit_gold_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_DEPOSIT_GOLD completo.

        Formato esperado:
        - Byte 0: PacketID (BANK_DEPOSIT_GOLD = 112)
        - Int32: Cantidad de oro a depositar

        Returns:
            ValidationResult con {"amount": int} si es válido.
        """
        amount = self.read_gold_amount(min_amount=0, max_amount=999999999)

        if self.has_errors() or amount is None:
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"amount": amount}, error_message=None)

    def validate_change_heading_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet CHANGE_HEADING completo.

        Formato esperado:
        - Byte 0: PacketID (CHANGE_HEADING = 37)
        - Byte: Heading (1-4)

        Returns:
            ValidationResult con {"heading": int} si es válido.
        """
        heading = self.read_heading()
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"heading": heading}, error_message=None)

    def validate_create_account_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet CREATE_ACCOUNT completo.

        Formato esperado:
        - Byte 0: PacketID (CREATE_ACCOUNT = 2)
        - String: Username (UTF-8, 3-20 chars)
        - String: Password (UTF-8, 6-32 chars)
        - Byte: Race
        - Int16: Unknown
        - Byte: Gender
        - Byte: Job/Class
        - Byte: Unknown
        - Int16: Head
        - String: Email (UTF-8, 1-100 chars)
        - Byte: Home

        Returns:
            ValidationResult con datos del personaje si es válido.
        """
        # Username
        username = self.read_string(min_length=3, max_length=20, encoding="utf-8")
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        # Password
        password = self.read_string(min_length=6, max_length=32, encoding="utf-8")
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        # Datos del personaje
        try:
            race = self.reader.read_byte()
            _ = self.reader.read_int16()  # Unknown
            gender = self.reader.read_byte()
            job = self.reader.read_byte()
            _ = self.reader.read_byte()  # Unknown
            head = self.reader.read_int16()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo datos del personaje: {e}")
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        # Email
        email = self.read_string(min_length=1, max_length=100, encoding="utf-8")
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        # Home
        try:
            home = self.reader.read_byte()
        except (ValueError, IndexError, struct.error) as e:
            self.errors.append(f"Error leyendo home: {e}")
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
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

    def validate_inventory_click_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet INVENTORY_CLICK completo.

        Formato esperado:
        - Byte 0: PacketID
        - Byte: Slot del inventario (1-20)

        Returns:
            ValidationResult con {"slot": int} si es válido.
        """
        slot = self.read_slot(min_slot=1, max_slot=20)
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )

        return ValidationResult(success=True, data={"slot": slot}, error_message=None)

    def validate_throw_dices_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet THROW_DICES completo.

        Formato esperado:
        - Byte 0: PacketID (THROW_DICES = 1)

        Returns:
            ValidationResult con {} (sin datos adicionales) si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_request_attributes_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_ATTRIBUTES completo.

        Formato esperado:
        - Byte 0: PacketID (REQUEST_ATTRIBUTES = 13)

        Returns:
            ValidationResult con {} (sin datos adicionales) si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_commerce_end_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet COMMERCE_END completo.

        Formato esperado:
        - Byte 0: PacketID (COMMERCE_END = 17)

        Returns:
            ValidationResult con {} (sin datos adicionales) si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_bank_end_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_END completo.

        Formato esperado:
        - Byte 0: PacketID (BANK_END = 21)

        Returns:
            ValidationResult con {} (sin datos adicionales) si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_request_position_update_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_POSITION_UPDATE completo.

        Formato esperado:
        - Byte 0: PacketID (REQUEST_POSITION_UPDATE = 7)

        Returns:
            ValidationResult con {} (sin datos adicionales) si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_gm_commands_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet GM_COMMANDS completo.

        Formato esperado:
        - Byte 0: PacketID (GM_COMMANDS)
        - Byte: Subcomando
        - String: Username
        - Int16: Map ID
        - Byte: X
        - Byte: Y

        Returns:
            ValidationResult con datos del comando si es válido.
        """
        result = self.validate_gm_teleport()
        if result is None:
            return ValidationResult(
                success=False, data=None, error_message="Error validando GM_COMMANDS"
            )

        subcommand, username, map_id, x, y = result
        return ValidationResult(
            success=True,
            data={
                "subcommand": subcommand,
                "username": username,
                "map_id": map_id,
                "x": x,
                "y": y,
            },
            error_message=None,
        )

    def validate_meditate_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet MEDITATE completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_request_stats_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_STATS completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_information_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet INFORMATION completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_request_motd_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_MOTD completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_uptime_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet UPTIME completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_online_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet ONLINE completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_quit_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet QUIT completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_ping_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet PING completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)

    def validate_ayuda_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet AYUDA completo (sin parámetros).

        Returns:
            ValidationResult con {} si es válido.
        """
        if self.has_errors():
            return ValidationResult(
                success=False, data=None, error_message=self.get_error_message()
            )
        return ValidationResult(success=True, data={}, error_message=None)
