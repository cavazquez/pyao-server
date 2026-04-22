"""Tests del PacketFramer (framing de packets sobre TCP).

Estos tests cubren explícitamente los bugs de la capa de transporte:

- Múltiples packets en un único recv.
- Packets partidos entre recvs.
- packet_id desconocido → conexión debe cortarse.
- Buffer overflow → conexión debe cortarse.
- Longitudes de string maliciosas (ej: 65535) no drenan memoria.
"""

from __future__ import annotations

import pytest

from src.network.packet_framer import (
    BufferOverflowError,
    PacketFramer,
    UnknownPacketError,
)
from src.network.packet_id import ClientPacketID


def _u16(n: int) -> bytes:
    return int.to_bytes(n, 2, "little", signed=False)


def _login_packet(username: str = "pepe", password: str = "secret") -> bytes:
    """Construye un packet LOGIN real como lo envía el cliente Godot.

    Layout: packet_id + unicode_str(user) + unicode_str(pwd) + 3 bytes trailer.
    """
    u = username.encode("utf-8")
    p = password.encode("utf-8")
    return (
        bytes([ClientPacketID.LOGIN])
        + _u16(len(u))
        + u
        + _u16(len(p))
        + p
        + bytes([0, 13, 0])  # build version trailer
    )


def _talk_packet(message: str) -> bytes:
    m = message.encode("utf-8")
    return bytes([ClientPacketID.TALK]) + _u16(len(m)) + m


class TestFixedLengthPackets:
    def test_ping_packet_single(self) -> None:
        framer = PacketFramer()
        framer.feed(bytes([ClientPacketID.PING]))

        assert framer.next_packet() == bytes([ClientPacketID.PING])
        assert framer.next_packet() is None

    def test_walk_packet_is_two_bytes(self) -> None:
        framer = PacketFramer()
        framer.feed(bytes([ClientPacketID.WALK, 0x03]))

        packet = framer.next_packet()
        assert packet == bytes([ClientPacketID.WALK, 0x03])

    def test_walk_truncated_waits_for_more(self) -> None:
        framer = PacketFramer()
        framer.feed(bytes([ClientPacketID.WALK]))

        assert framer.next_packet() is None
        framer.feed(bytes([0x03]))
        assert framer.next_packet() == bytes([ClientPacketID.WALK, 0x03])


class TestMultiplePacketsInOneChunk:
    """Regresión del bug real: el servidor descartaba packets extras."""

    def test_two_pings_in_one_recv(self) -> None:
        framer = PacketFramer()
        chunk = bytes([ClientPacketID.PING, ClientPacketID.PING])
        framer.feed(chunk)

        assert framer.next_packet() == bytes([ClientPacketID.PING])
        assert framer.next_packet() == bytes([ClientPacketID.PING])
        assert framer.next_packet() is None

    def test_walk_followed_by_attack(self) -> None:
        framer = PacketFramer()
        framer.feed(bytes([ClientPacketID.WALK, 0x02, ClientPacketID.ATTACK]))

        assert framer.next_packet() == bytes([ClientPacketID.WALK, 0x02])
        assert framer.next_packet() == bytes([ClientPacketID.ATTACK])
        assert framer.next_packet() is None

    def test_login_followed_by_ping(self) -> None:
        framer = PacketFramer()
        login = _login_packet()
        framer.feed(login + bytes([ClientPacketID.PING]))

        assert framer.next_packet() == login
        assert framer.next_packet() == bytes([ClientPacketID.PING])
        assert framer.next_packet() is None


class TestPartialPackets:
    """Regresión: el servidor asumía 1 recv = 1 packet completo."""

    def test_split_login_across_three_feeds(self) -> None:
        framer = PacketFramer()
        login = _login_packet()

        framer.feed(login[:1])  # solo packet_id
        assert framer.next_packet() is None

        framer.feed(login[1:5])  # parte del username
        assert framer.next_packet() is None

        framer.feed(login[5:])
        assert framer.next_packet() == login
        assert framer.next_packet() is None

    def test_split_talk_across_feeds(self) -> None:
        framer = PacketFramer()
        packet = _talk_packet("hola mundo")

        framer.feed(packet[:3])  # packet_id + primer byte del length
        assert framer.next_packet() is None

        framer.feed(packet[3:])
        assert framer.next_packet() == packet


class TestUnknownPacket:
    """Un packet_id no soportado debe cortar la conexión.

    La alternativa (saltar bytes arbitrarios) desincroniza el stream y abre
    un vector de evasión de validación.
    """

    def test_unknown_packet_id_raises(self) -> None:
        framer = PacketFramer()
        framer.feed(bytes([0xFF, 0x00, 0x00]))

        with pytest.raises(UnknownPacketError) as exc:
            framer.next_packet()
        assert exc.value.packet_id == 0xFF


class TestBufferOverflowProtection:
    def test_buffer_overflow_raises(self) -> None:
        framer = PacketFramer()
        framer.feed(bytes([ClientPacketID.PING]) * (PacketFramer.MAX_BUFFER_BYTES - 1))

        with pytest.raises(BufferOverflowError):
            framer.feed(b"\x00" * 2)

    def test_malicious_string_length_triggers_overflow(self) -> None:
        """Un cliente malicioso anuncia length=65535 pero no envía bytes.

        El framer no debe retener memoria indefinidamente: al próximo feed
        el buffer debe sobrepasar el máximo y cortar la conexión.
        """
        framer = PacketFramer()
        # TALK con longitud anunciada = 65000 (>MAX_BUFFER_BYTES)
        framer.feed(bytes([ClientPacketID.TALK]) + _u16(65000))

        # El probe indica "necesito 65k bytes" → next_packet devuelve None.
        assert framer.next_packet() is None

        # Al seguir enviando bytes eventualmente MAX_BUFFER_BYTES corta.
        with pytest.raises(BufferOverflowError):
            framer.feed(b"x" * PacketFramer.MAX_BUFFER_BYTES)


class TestVariableLengthPackets:
    def test_party_message_variable_length(self) -> None:
        framer = PacketFramer()
        msg = b"equipo activo"
        packet = bytes([ClientPacketID.PARTY_MESSAGE]) + _u16(len(msg)) + msg
        framer.feed(packet + bytes([ClientPacketID.PING]))

        assert framer.next_packet() == packet
        assert framer.next_packet() == bytes([ClientPacketID.PING])

    def test_gm_commands_has_string_and_coords(self) -> None:
        framer = PacketFramer()
        # subcmd(1) + username_str + map_id(i16) + x(1) + y(1)
        username = b"admin"
        packet = (
            bytes([ClientPacketID.GM_COMMANDS, 0x01])
            + _u16(len(username))
            + username
            + _u16(1)
            + bytes([50, 50])
        )
        framer.feed(packet)

        assert framer.next_packet() == packet

    def test_cast_spell_godot_client_format_is_2_bytes(self) -> None:
        """El cliente Godot envía packet_id + slot (2 bytes).

        El servidor soporta un formato extendido de 7 bytes con coordenadas,
        pero ese camino es dead code con el cliente actual. Lo importante
        para el framer es respetar lo que el cliente envía realmente.
        """
        framer = PacketFramer()
        packet = bytes([ClientPacketID.CAST_SPELL, 5])
        framer.feed(packet + bytes([ClientPacketID.PING]))

        assert framer.next_packet() == packet
        assert framer.next_packet() == bytes([ClientPacketID.PING])

    def test_party_join_is_fixed_single_byte(self) -> None:
        """El cliente Godot envía PARTY_JOIN sin payload (solo 1 byte)."""
        framer = PacketFramer()
        framer.feed(bytes([ClientPacketID.PARTY_JOIN, ClientPacketID.PING]))

        assert framer.next_packet() == bytes([ClientPacketID.PARTY_JOIN])
        assert framer.next_packet() == bytes([ClientPacketID.PING])


class TestEmptyAndNoOpFeeds:
    def test_empty_feed_is_noop(self) -> None:
        framer = PacketFramer()
        framer.feed(b"")
        assert framer.next_packet() is None
        assert framer.buffer_size == 0

    def test_next_packet_on_empty_buffer(self) -> None:
        framer = PacketFramer()
        assert framer.next_packet() is None
