"""Mixins para PacketReader con métodos de lectura y validación de tipos."""

import logging
import struct

logger = logging.getLogger(__name__)


class PacketReaderMixin:
    """Mixins para lectura y validación de tipos básicos del packet.

    Proporciona métodos para leer slots, quantities, coordenadas, etc.
    con validación de rangos.
    """

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

    MAX_GOLD_AMOUNT = 999999999

    def read_gold_amount(
        self, min_amount: int = 0, max_amount: int = MAX_GOLD_AMOUNT
    ) -> int | None:
        """Lee y valida una cantidad de oro.

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
                self.errors.append(
                    f"Cantidad de oro inválida: {amount} "
                    f"(debe estar entre {min_amount}-{max_amount})"
                )
                return None
            return amount

    def read_username(self, max_length: int = 20) -> str | None:
        """Lee y valida un nombre de usuario.

        Args:
            max_length: Longitud máxima permitida (default: 20).

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
                self.errors.append(f"Username muy largo: {len(username)} (máximo: {max_length})")
                return None
            return username

    def read_coordinates(self, max_x: int = 100, max_y: int = 100) -> tuple[int, int] | None:
        """Lee y valida coordenadas.

        Args:
            max_x: Coordenada X máxima válida (default: 100).
            max_y: Coordenada Y máxima válida (default: 100).

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
                self.errors.append(
                    f"Coordenadas inválidas: ({x}, {y}) "
                    f"(deben estar entre 1-{max_x}, 1-{max_y})"
                )
                return None
            return (x, y)

    def read_password(self, min_length: int = 6, max_length: int = 32) -> str | None:
        """Lee y valida una contraseña.

        Args:
            min_length: Longitud mínima (default: 6).
            max_length: Longitud máxima (default: 32).

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
                self.errors.append(
                    f"Contraseña muy corta: {len(password)} (mínimo: {min_length})"
                )
                return None
            if len(password) > max_length:
                self.errors.append(
                    f"Contraseña muy larga: {len(password)} (máximo: {max_length})"
                )
                return None
            if not password:
                self.errors.append("Contraseña vacía")
                return None
            return password

    def read_spell_slot(self, max_slot: int = 35) -> int | None:
        """Lee y valida un slot de hechizo.

        Args:
            max_slot: Slot máximo válido (default: 35).

        Returns:
            Slot de hechizo válido o None si hay error.
        """
        return self.read_slot(min_slot=1, max_slot=max_slot)

    def read_heading(self) -> int | None:
        """Lee y valida una dirección (1-4).

        Returns:
            Dirección válida (1=Norte, 2=Este, 3=Sur, 4=Oeste) o None si hay error.
        """
        max_heading = 4
        try:
            heading = self.reader.read_byte()
            if heading < 1 or heading > max_heading:
                self.errors.append(f"Dirección inválida: {heading} (debe ser 1-4)")
                return None
        except struct.error as e:
            self.errors.append(f"Error al leer heading: {e}")
            return None
        else:
            return heading

    def read_string(
        self,
        min_length: int = 1,
        max_length: int = 255,
        encoding: str = "utf-8",
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
            length = self.reader.read_int16()

            if length < min_length:
                self.errors.append(f"String muy corto (mínimo {min_length} caracteres)")
                return None
            if length > max_length:
                self.errors.append(f"String muy largo (máximo {max_length} caracteres)")
                return None
            if len(self.reader.data) < self.reader.offset + length:
                self.errors.append("Datos insuficientes para leer string")
                return None

            string_bytes = self.reader.data[self.reader.offset : self.reader.offset + length]
            self.reader.offset += length
            return string_bytes.decode(encoding)
        except (ValueError, UnicodeDecodeError) as e:
            self.errors.append(f"Error al decodificar string: {e}")
            return None
        except struct.error as e:
            self.errors.append(f"Error al leer longitud del string: {e}")
            return None

    MAX_MAP_ID = 1000
    MAX_COORD = 100
    MAX_GM_USERNAME = 20

    def validate_gm_teleport(self) -> tuple[int, str, int, int, int] | None:
        """Valida packet GM_COMMANDS (teletransporte).

        Formato esperado:
        - Byte: Subcomando GM
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

        if map_id < 1 or map_id > self.MAX_MAP_ID:
            self.errors.append(f"Map ID inválido: {map_id} (debe estar entre 1-{self.MAX_MAP_ID})")
            return None

        if not (1 <= x <= self.MAX_COORD and 1 <= y <= self.MAX_COORD):
            self.errors.append(
                f"Posición inválida: ({x}, {y}) (debe estar entre 1-{self.MAX_COORD})"
            )
            return None

        if not username or len(username) > self.MAX_GM_USERNAME:
            self.errors.append(
                f"Username inválido: '{username}' (longitud: {len(username)})"
            )
            return None

        return subcommand, username, map_id, x, y
