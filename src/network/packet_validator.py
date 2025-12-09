"""Validador de paquetes para centralizar parsing y validación."""

import logging
import struct
from typing import TYPE_CHECKING, Any

from src.network.packet_id import ClientPacketID
from src.network.validation_result import ValidationResult
from src.network.validators.base import ValidationContext
from src.network.validators.registry import get_packet_validator_registry

if TYPE_CHECKING:
    from src.network.packet_reader import PacketReader

logger = logging.getLogger(__name__)


class PacketValidator:
    """Valida y parsea packets usando PacketReader.

    Centraliza la lógica de parsing y validación para evitar duplicación
    en las tasks.

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

    def _validate_with_registry(self, packet_id: int) -> ValidationResult[dict[str, Any]]:
        """Helper que delega en el registry.

        Returns:
            ValidationResult del validador o error si no existe.
        """
        validator = get_packet_validator_registry().get_validator(packet_id)
        if validator is None:
            return ValidationResult(
                success=False, data=None, error_message="Validador no encontrado"
            )

        context = ValidationContext(reader=self.reader, errors=self.errors.copy())
        result = validator.validate(context)
        self.errors = context.errors
        return result

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

    def validate_walk_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet WALK.

        Returns:
            ValidationResult con heading o error.
        """
        return self._validate_with_registry(ClientPacketID.WALK)

    def validate_attack_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet ATTACK.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.ATTACK)

    def validate_move_spell_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet MOVE_SPELL (usa registry).

        Returns:
            ValidationResult con slot y upwards o error.
        """
        return self._validate_with_registry(ClientPacketID.MOVE_SPELL)

    def validate_login_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet LOGIN.

        Returns:
            ValidationResult con credenciales o error.
        """
        return self._validate_with_registry(ClientPacketID.LOGIN)

    def validate_cast_spell_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet CAST_SPELL.

        Returns:
            ValidationResult con slot o error.
        """
        return self._validate_with_registry(ClientPacketID.CAST_SPELL)

    def validate_spell_info_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet SPELL_INFO.

        Returns:
            ValidationResult con slot o error.
        """
        return self._validate_with_registry(ClientPacketID.SPELL_INFO)

    def validate_drop_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet DROP.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        return self._validate_with_registry(ClientPacketID.DROP)

    def validate_pickup_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet PICK_UP.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.PICK_UP)

    def validate_talk_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet TALK.

        Returns:
            ValidationResult con mensaje o error.
        """
        return self._validate_with_registry(ClientPacketID.TALK)

    def validate_double_click_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet DOUBLE_CLICK.

        Returns:
            ValidationResult con slot o error.
        """
        return self._validate_with_registry(ClientPacketID.DOUBLE_CLICK)

    def validate_left_click_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet LEFT_CLICK.

        Returns:
            ValidationResult con coordenadas o error.
        """
        return self._validate_with_registry(ClientPacketID.LEFT_CLICK)

    def validate_equip_item_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet EQUIP_ITEM.

        Returns:
            ValidationResult con slot o error.
        """
        return self._validate_with_registry(ClientPacketID.EQUIP_ITEM)

    def validate_use_item_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet USE_ITEM.

        Returns:
            ValidationResult con slot o error.
        """
        return self._validate_with_registry(ClientPacketID.USE_ITEM)

    def validate_commerce_buy_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet COMMERCE_BUY.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        return self._validate_with_registry(ClientPacketID.COMMERCE_BUY)

    def validate_commerce_sell_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet COMMERCE_SELL.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        return self._validate_with_registry(ClientPacketID.COMMERCE_SELL)

    def validate_bank_deposit_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_DEPOSIT.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        return self._validate_with_registry(ClientPacketID.BANK_DEPOSIT)

    def validate_bank_extract_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_EXTRACT_ITEM.

        Returns:
            ValidationResult con slot y cantidad o error.
        """
        return self._validate_with_registry(ClientPacketID.BANK_EXTRACT_ITEM)

    def validate_bank_extract_gold_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_EXTRACT_GOLD.

        Returns:
            ValidationResult con amount o error.
        """
        return self._validate_with_registry(ClientPacketID.BANK_EXTRACT_GOLD)

    def validate_bank_deposit_gold_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_DEPOSIT_GOLD.

        Returns:
            ValidationResult con amount o error.
        """
        return self._validate_with_registry(ClientPacketID.BANK_DEPOSIT_GOLD)

    def validate_change_heading_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet CHANGE_HEADING.

        Returns:
            ValidationResult con heading o error.
        """
        return self._validate_with_registry(ClientPacketID.CHANGE_HEADING)

    def validate_create_account_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet CREATE_ACCOUNT.

        Returns:
            ValidationResult con datos o error.
        """
        return self._validate_with_registry(ClientPacketID.CREATE_ACCOUNT)

    def validate_inventory_click_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet INVENTORY_CLICK.

        Returns:
            ValidationResult con slot o error.
        """
        return self._validate_with_registry(ClientPacketID.LEFT_CLICK)

    def validate_throw_dices_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet THROW_DICES.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.THROW_DICES)

    def validate_request_attributes_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_ATTRIBUTES.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.REQUEST_ATTRIBUTES)

    def validate_commerce_end_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet COMMERCE_END.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.COMMERCE_END)

    def validate_bank_end_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet BANK_END.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.BANK_END)

    def validate_request_position_update_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_POSITION_UPDATE.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.REQUEST_POSITION_UPDATE)

    def validate_gm_commands_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet GM_COMMANDS.

        Returns:
            ValidationResult con datos GM o error.
        """
        return self._validate_with_registry(ClientPacketID.GM_COMMANDS)

    def validate_meditate_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet MEDITATE.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.MEDITATE)

    def validate_request_stats_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_STATS.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.REQUEST_STATS)

    def validate_information_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet INFORMATION.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.INFORMATION)

    def validate_request_motd_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet REQUEST_MOTD.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.REQUEST_MOTD)

    def validate_uptime_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet UPTIME.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.UPTIME)

    def validate_online_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet ONLINE.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.ONLINE)

    def validate_quit_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet QUIT.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.QUIT)

    def validate_ping_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet PING.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.PING)

    def validate_ayuda_packet(self) -> ValidationResult[dict[str, Any]]:
        """Valida packet AYUDA.

        Returns:
            ValidationResult vacío o error.
        """
        return self._validate_with_registry(ClientPacketID.AYUDA)

    # Métodos de validación específicos para patrones comunes
    # Estos métodos reemplazan a los métodos read_* para una API consistente

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
        # Validar slot
        slot_result = self.validate_slot(min_slot, max_slot)
        if not slot_result.success:
            return ValidationResult(
                success=False,
                data=None,
                error_message=slot_result.error_message,
            )

        # Validar cantidad
        qty_result = self.validate_quantity(min_qty, max_qty)
        if not qty_result.success:
            return ValidationResult(
                success=False,
                data=None,
                error_message=qty_result.error_message,
            )

        # Validar que los datos no son None (should never happen when success=True)
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
            # Guardar offset original

            # Leer longitud primero
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

            # Validar longitud
            if length < min_length or length > max_length:
                return ValidationResult(
                    success=False,
                    data=None,
                    error_message=(
                        f"Longitud de string inválida: {length} "
                        f"(debe estar entre {min_length}-{max_length})"
                    ),
                )

            # Avanzar offset después de leer longitud
            self.reader.offset += 2

            # Leer bytes del string
            string_bytes = self.reader.data[self.reader.offset : self.reader.offset + length]

            # Validar que hay suficientes bytes
            if len(string_bytes) < length:
                return ValidationResult(
                    success=False,
                    data=None,
                    error_message=(
                        f"String truncado: se esperaban {length} bytes, hay {len(string_bytes)}"
                    ),
                )

            # Decodificar con la codificación especificada
            string_value = string_bytes.decode(encoding)

            # Actualizar offset del reader
            self.reader.offset += length

        except (ValueError, IndexError, struct.error, UnicodeDecodeError) as e:
            return ValidationResult(
                success=False, data=None, error_message=f"Error leyendo string: {e}"
            )

        if not string_value:
            return ValidationResult(success=False, data=None, error_message="String vacío")

        return ValidationResult(success=True, data=string_value, error_message=None)
