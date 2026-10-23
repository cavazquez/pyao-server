"""Tests del PacketFramer (framing de packets sobre TCP).

Estos tests cubren explícitamente los bugs de la capa de transporte:

- Múltiples packets en un único recv.
- Packets partidos entre recvs.
- packet_id desconocido → conexión debe cortarse.
- Buffer overflow → conexión debe cortarse.
- Longitudes de string maliciosas (ej: 65535) no drenan memoria.
"""

from __future__ import annotations

import struct

import pytest

from src.network.packet_framer import (
    BufferOverflowError,
    InvalidLengthError,
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
    u = username.encode("latin-1")
    p = password.encode("latin-1")
    return (
        bytes([ClientPacketID.LOGIN])
        + _u16(len(u))
        + u
        + _u16(len(p))
        + p
        + bytes([0, 13, 0])  # build version trailer
    )


def _talk_packet(message: str) -> bytes:
    m = message.encode("latin-1")
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

        # Rechazar con sólo el prefijo: no esperar a llenar el buffer.
        with pytest.raises(InvalidLengthError):
            framer.next_packet()


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
            bytes([ClientPacketID.GM_COMMANDS, 11])
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

    def test_party_join_consumes_canonical_nickname(self) -> None:
        """La actualización coordinada usa nickname u16 + Latin-1."""
        framer = PacketFramer()
        packet = bytes([ClientPacketID.PARTY_JOIN]) + _u16(3) + b"Ana"
        framer.feed(packet + bytes([ClientPacketID.PING]))
        assert framer.next_packet() == packet
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


def test_double_click_and_safe_toggle_preserve_following_packet() -> None:
    """Las dos regresiones respetan sus fronteras aun concatenadas."""
    framer = PacketFramer()
    framer.feed(bytes([27, 50, 51, 10, 6, 2]))
    assert [framer.next_packet() for _ in range(3)] == [bytes([27, 50, 51]), b"\x0a", b"\x06\x02"]


def test_every_supported_handler_at_every_boundary() -> None:
    """Ningún handler queda sin regla y ningún split roba bytes del PING siguiente."""
    from src.network.packet_framer import CONTRACT  # ruff: ignore[import-outside-top-level]
    from src.network.packet_handlers import TASK_HANDLERS  # ruff: ignore[import-outside-top-level]

    for packet_id in TASK_HANDLERS:
        entry = CONTRACT["directions"]["client"][str(packet_id)]
        packet = bytes([packet_id])
        fields = entry["fields"]
        if "variants" in entry:
            packet += b"\x0b"
            fields = entry["variants"]["11"]
        for field in fields:
            if field["type"] == "str16":
                text = b"a" * max(1, field.get("min_bytes", 0))
                packet += _u16(len(text)) + text
            else:
                packet += struct.pack(
                    "<" + {"u8": "B", "i16": "h", "i32": "i"}[field["type"]], field.get("min", 1)
                )
        for split in range(1, len(packet)):
            framer = PacketFramer()
            framer.feed(packet[:split])
            assert framer.next_packet() is None, (packet_id, split)
            framer.feed(packet[split:] + b"\x77")
            assert framer.next_packet() == packet, (packet_id, split)
            assert framer.next_packet() == b"\x77"
            assert framer.next_packet() is None


@pytest.mark.parametrize("data", [b"\x7a\x01", b"\x7a\xff"])
def test_unknown_gm_subcommand_fails_without_waiting(data: bytes) -> None:
    """Un subcomando no declarado corta inmediatamente."""
    from src.network.packet_framer import InvalidVariantError  # ruff: ignore[import-outside-top-level]

    framer = PacketFramer()
    framer.feed(data)
    with pytest.raises(InvalidVariantError):
        framer.next_packet()
