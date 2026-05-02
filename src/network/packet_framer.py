"""Framing de packets del protocolo Argentum Online sobre TCP.

El protocolo AO no usa length prefix: cada packet empieza con un byte ``packet_id``
y su longitud se deduce de la semántica de los campos. Como TCP es un stream,
un ``recv`` puede contener:

- Un packet completo (caso feliz).
- Dos o más packets concatenados.
- Un packet parcial (dividido en varios ``recv``).
- Cualquier combinación anterior.

``PacketFramer`` acumula bytes en un buffer y extrae packets completos
siguiendo tablas de longitud deterministas por ``packet_id``. Tiene tres
responsabilidades:

1. Determinar la longitud del próximo packet (``_peek_packet_length``).
2. Detectar packet_ids desconocidos para cerrar la conexión (defensivo: no
   podemos "saltar" bytes sin saber cuántos consume el packet, así que
   preferimos cortar antes que desincronizar).
3. Aplicar un límite duro de buffer (``MAX_BUFFER_BYTES``) para evitar que
   un cliente malicioso retenga memoria indefinida con un packet "pendiente".

Este módulo es puro: no hace I/O ni depende de asyncio.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from src.network.packet_id import ClientPacketID


class FramingError(Exception):
    """Error irrecuperable de framing: se debe cerrar la conexión."""


class UnknownPacketError(FramingError):
    """El primer byte del buffer no corresponde a un packet_id soportado."""

    def __init__(self, packet_id: int) -> None:
        """Construye el error con el packet_id no reconocido."""
        super().__init__(f"packet_id desconocido: {packet_id}")
        self.packet_id = packet_id


class BufferOverflowError(FramingError):
    """El buffer superó el máximo permitido sin completar un packet."""


class PacketFramer:
    """Extrae packets completos de un stream TCP.

    Uso típico::

        framer = PacketFramer()
        framer.feed(chunk)
        while (packet := framer.next_packet()) is not None:
            process(packet)

    ``next_packet`` devuelve ``None`` cuando el buffer actual no alcanza para
    un packet completo (necesita más bytes). Si detecta un estado irrecuperable
    lanza ``FramingError``; el caller debe cerrar la conexión.
    """

    # Límite duro del buffer pendiente. En la práctica el packet variable más
    # grande (CREATE_ACCOUNT) apenas supera los 200 bytes, con un margen
    # holgado para packets de chat (TALK, PARTY_MESSAGE) hasta 255 chars.
    MAX_BUFFER_BYTES: ClassVar[int] = 4 * 1024

    # Longitudes fijas (incluido el byte de packet_id).
    _FIXED_LENGTHS: ClassVar[dict[int, int]] = {
        # Packets sin parámetros (solo packet_id).
        ClientPacketID.THROW_DICES: 1,
        ClientPacketID.REQUEST_POSITION_UPDATE: 1,
        ClientPacketID.ATTACK: 1,
        ClientPacketID.PICK_UP: 1,
        ClientPacketID.REQUEST_ATTRIBUTES: 1,
        ClientPacketID.REQUEST_SKILLS: 1,
        ClientPacketID.COMMERCE_END: 1,
        ClientPacketID.USER_COMMERCE_END: 1,
        ClientPacketID.USER_COMMERCE_CONFIRM: 1,
        ClientPacketID.BANK_END: 1,
        ClientPacketID.USER_COMMERCE_OK: 1,
        ClientPacketID.USER_COMMERCE_REJECT: 1,
        ClientPacketID.CLAN_REQUEST_DETAILS: 1,
        ClientPacketID.CLAN_LEAVE: 1,
        ClientPacketID.ONLINE: 1,
        ClientPacketID.QUIT: 1,
        ClientPacketID.MEDITATE: 1,
        ClientPacketID.AYUDA: 1,
        ClientPacketID.REQUEST_STATS: 1,
        ClientPacketID.COMMERCE_START: 1,
        ClientPacketID.BANK_START: 1,
        ClientPacketID.INFORMATION: 1,
        ClientPacketID.REQUEST_MOTD: 1,
        ClientPacketID.UPTIME: 1,
        ClientPacketID.PARTY_LEAVE: 1,
        ClientPacketID.PARTY_CREATE: 1,
        ClientPacketID.PING: 1,
        # Packets con 1 byte de payload.
        ClientPacketID.WALK: 2,
        ClientPacketID.USE_ITEM: 2,
        ClientPacketID.EQUIP_ITEM: 2,
        ClientPacketID.CHANGE_HEADING: 2,
        ClientPacketID.WORK: 2,
        ClientPacketID.DOUBLE_CLICK: 2,
        ClientPacketID.SPELL_INFO: 2,
        # Packets con 2 bytes de payload.
        ClientPacketID.LEFT_CLICK: 3,
        ClientPacketID.MOVE_SPELL: 3,
        # Packets con 3 bytes de payload.
        ClientPacketID.WORK_LEFT_CLICK: 4,
        ClientPacketID.USER_COMMERCE_OFFER: 4,  # slot(1) + quantity(2)
        ClientPacketID.DROP: 4,  # slot(1) + quantity(2)
        ClientPacketID.COMMERCE_BUY: 4,  # slot(1) + quantity(2)
        ClientPacketID.COMMERCE_SELL: 4,  # slot(1) + quantity(2)
        ClientPacketID.BANK_EXTRACT_ITEM: 4,  # slot(1) + quantity(2)
        ClientPacketID.BANK_DEPOSIT: 4,  # slot(1) + quantity(2)
        # Packets con 4 bytes de payload.
        ClientPacketID.BANK_EXTRACT_GOLD: 5,  # amount(4)
        ClientPacketID.BANK_DEPOSIT_GOLD: 5,  # amount(4)
        # CAST_SPELL: el cliente Godot envía packet_id + slot (2 bytes). El
        # código del servidor aún soporta un formato extendido de 7 bytes
        # con target_x/y que actualmente no se usa (dead code).
        ClientPacketID.CAST_SPELL: 2,
        # PARTY_JOIN: el cliente Godot envía solo el packet_id (el target se
        # obtiene del último click izquierdo). El servidor intenta leer un
        # nickname que nunca llega: bug aparte documentado en docs/AUDITORIA.md.
        ClientPacketID.PARTY_JOIN: 1,
    }

    def __init__(self) -> None:
        """Inicializa el framer con buffer vacío."""
        self._buffer = bytearray()

    # ----------------------------------------------------------------- API

    def feed(self, data: bytes) -> None:
        """Agrega bytes recibidos del socket al buffer interno.

        Args:
            data: Bytes crudos recién recibidos del socket.

        Raises:
            BufferOverflowError: Si el buffer supera ``MAX_BUFFER_BYTES``.
        """
        if not data:
            return
        if len(self._buffer) + len(data) > self.MAX_BUFFER_BYTES:
            msg = (
                f"Buffer de framing superó {self.MAX_BUFFER_BYTES} bytes "
                f"(actual={len(self._buffer)}, recibido={len(data)})"
            )
            raise BufferOverflowError(msg)
        self._buffer.extend(data)

    def next_packet(self) -> bytes | None:
        """Extrae un packet completo del buffer si es posible.

        Returns:
            Los bytes del próximo packet (incluido packet_id) o ``None`` si
            hacen falta más bytes.

        Raises:
            UnknownPacketError: Si el ``packet_id`` no está soportado.
        """
        if not self._buffer:
            return None

        packet_id = self._buffer[0]
        length = self._peek_packet_length(bytes(self._buffer), packet_id)

        if length is None:
            # Necesitamos más bytes: probe indica incompleto.
            return None

        if length <= 0:
            # Contrato de probe: length > 0 siempre que packet_id sea conocido.
            raise UnknownPacketError(packet_id)

        if length > len(self._buffer):
            return None  # Packet conocido pero truncado.

        packet = bytes(self._buffer[:length])
        del self._buffer[:length]
        return packet

    @property
    def buffer_size(self) -> int:
        """Bytes pendientes (útil para métricas)."""
        return len(self._buffer)

    # ------------------------------------------------------- longitud probes

    @classmethod
    def _peek_packet_length(cls, buf: bytes, packet_id: int) -> int | None:
        """Devuelve la longitud total del próximo packet, o None si incompleto.

        Contrato:
        - Si devuelve un entero positivo: esa es la longitud exacta del packet.
          El caller debe verificar si el buffer la contiene.
        - Si devuelve ``None``: hacen falta más bytes para decidir.
        - Si devuelve ``-1``: ``packet_id`` desconocido (señal para cerrar).

        Returns:
            Longitud en bytes, ``None`` si el buffer está incompleto,
            ``-1`` si el ``packet_id`` es desconocido.
        """
        if packet_id in cls._FIXED_LENGTHS:
            return cls._FIXED_LENGTHS[packet_id]

        probe = cls._VARIABLE_PROBES.get(packet_id)
        if probe is None:
            return -1  # packet_id desconocido

        return probe(buf)

    # Probes de longitud para packets variables.
    # Cada probe recibe el buffer crudo (empezando por packet_id) y devuelve:
    # - int > 0: longitud total del packet
    # - None: buffer incompleto (hace falta más bytes)

    @staticmethod
    def _probe_login(buf: bytes) -> int | None:
        """LOGIN (0) según el cliente Godot.

        Layout (WriteLoginExistingCharacter):
            1 byte  packet_id
            2+U     username (Utils.PutUnicodeString: int16 LE + bytes latin-1)
            2+P     password
            1 byte  build version major (0)
            1 byte  build version minor (13)
            1 byte  build version patch (0)

        Returns:
            Longitud total en bytes o ``None`` si el buffer está incompleto.
        """
        after_strings = _probe_n_strings(buf, start_offset=1, num_strings=2)
        if after_strings is None:
            return None
        trailer = 3  # 3 bytes de versión de build
        return after_strings + trailer

    @staticmethod
    def _probe_create_account(buf: bytes) -> int | None:
        """CREATE_ACCOUNT (2) según el cliente Godot (WriteLoginNewChar).

        Layout:
            1 byte  packet_id
            2+U     username
            2+P     password
            3 bytes versión de build (0, 13, 0)
            1 byte  race
            1 byte  gender
            1 byte  job
            2 bytes head (int16)
            2+E     email
            1 byte  home

        Returns:
            Longitud total en bytes o ``None`` si el buffer está incompleto.
        """
        after_creds = _probe_n_strings(buf, start_offset=1, num_strings=2)
        if after_creds is None:
            return None
        # 3 bytes versión + race + gender + job + head(2) = 8 bytes
        char_data_len = 8
        email_offset = after_creds + char_data_len
        after_email = _probe_n_strings(buf, start_offset=email_offset, num_strings=1)
        if after_email is None:
            return None
        return after_email + 1  # + 1 byte de home

    @staticmethod
    def _probe_single_string(buf: bytes) -> int | None:
        """Packet con un único string variable (TALK, PARTY_MESSAGE, PARTY_KICK, etc.).

        Returns:
            Longitud total en bytes o ``None`` si el buffer está incompleto.
        """
        return _probe_n_strings(buf, start_offset=1, num_strings=1)

    @staticmethod
    def _probe_gm_commands(buf: bytes) -> int | None:
        """GM_COMMANDS (122): subcmd(1) + username(str) + map_id(i16) + x(1) + y(1).

        Returns:
            Longitud total en bytes o ``None`` si el buffer está incompleto.
        """
        # 1 packet_id + 1 subcmd + str + 2 + 1 + 1; str empieza en offset 2
        after_string = _probe_n_strings(buf, start_offset=2, num_strings=1)
        if after_string is None:
            return None
        return after_string + 4  # map_id(2) + x(1) + y(1)

    _VARIABLE_PROBES: ClassVar[dict[int, Callable[[bytes], int | None]]]


def _probe_n_strings(buf: bytes, start_offset: int, num_strings: int) -> int | None:
    """Avanza ``num_strings`` campos (u16 length + bytes) en el buffer.

    Args:
        buf: Buffer completo con packet_id en [0].
        start_offset: Offset desde donde empezar a leer el primer string.
        num_strings: Cantidad de strings a recorrer.

    Returns:
        Offset justo después del último string, o ``None`` si el buffer no
        alcanza.
    """
    offset = start_offset
    for _ in range(num_strings):
        # Necesitamos 2 bytes para la longitud.
        if len(buf) < offset + 2:
            return None
        length = int.from_bytes(buf[offset : offset + 2], "little", signed=False)
        offset += 2
        # Protección: longitudes absurdas cortan el framing.
        if length > PacketFramer.MAX_BUFFER_BYTES:
            # Devolver una longitud imposible de satisfacer fuerza a que el
            # buffer se llene y dispare BufferOverflowError en la próxima feed,
            # cerrando la conexión. Evita que un cliente malicioso anuncie
            # longitudes gigantes para retener memoria.
            return PacketFramer.MAX_BUFFER_BYTES + 1
        if len(buf) < offset + length:
            return None
        offset += length
    return offset


PacketFramer._VARIABLE_PROBES = {  # noqa: SLF001 - inicialización diferida necesaria
    ClientPacketID.LOGIN: PacketFramer._probe_login,  # noqa: SLF001
    ClientPacketID.CREATE_ACCOUNT: PacketFramer._probe_create_account,  # noqa: SLF001
    ClientPacketID.TALK: PacketFramer._probe_single_string,  # noqa: SLF001
    ClientPacketID.PARTY_JOIN: PacketFramer._probe_single_string,  # noqa: SLF001
    ClientPacketID.PARTY_MESSAGE: PacketFramer._probe_single_string,  # noqa: SLF001
    ClientPacketID.PARTY_KICK: PacketFramer._probe_single_string,  # noqa: SLF001
    ClientPacketID.PARTY_SET_LEADER: PacketFramer._probe_single_string,  # noqa: SLF001
    ClientPacketID.PARTY_ACCEPT_MEMBER: PacketFramer._probe_single_string,  # noqa: SLF001
    ClientPacketID.GM_COMMANDS: PacketFramer._probe_gm_commands,  # noqa: SLF001
}
