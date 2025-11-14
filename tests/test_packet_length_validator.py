"""Tests para PacketLengthValidator."""

import pytest

from src.utils.packet_length_validator import PacketLengthValidator


class TestPacketLengthValidator:
    """Tests para la clase PacketLengthValidator."""

    @pytest.mark.asyncio
    async def test_validate_min_length_valid_packets(self):
        """Testea paquetes válidos con longitud mínima correcta."""
        # Packet sin datos (solo PacketID)
        assert await PacketLengthValidator.validate_min_length(b"\x01", 1)  # THROW_DICES
        assert await PacketLengthValidator.validate_min_length(b"\x16", 22)  # PING

        # Packet con 1 byte de datos
        assert await PacketLengthValidator.validate_min_length(b"\x06\x01", 6)  # WALK con heading

        # Packet con 2 bytes de datos (corregido)
        assert await PacketLengthValidator.validate_min_length(
            b"\x03\x05", 3
        )  # DOUBLE_CLICK con target

        # Packet con 3 bytes de datos
        assert await PacketLengthValidator.validate_min_length(b"\x1a\x05\x10", 26)  # LEFT_CLICK

    @pytest.mark.asyncio
    async def test_validate_min_length_invalid_packets(self):
        """Testea paquetes inválidos con longitud insuficiente."""
        # Packet vacío
        assert not await PacketLengthValidator.validate_min_length(b"", 1)

        # Packet sin datos cuando se esperan datos
        assert not await PacketLengthValidator.validate_min_length(b"\x06", 6)  # WALK sin heading
        assert not await PacketLengthValidator.validate_min_length(
            b"\x13", 19
        )  # EQUIP_ITEM sin slot

        # Packet truncado
        assert not await PacketLengthValidator.validate_min_length(
            b"\x1a\x05", 26
        )  # LEFT_CLICK sin Y

    @pytest.mark.asyncio
    async def test_validate_generic_min_length_valid(self):
        """Testea validación genérica con longitud correcta."""
        assert await PacketLengthValidator.validate_generic_min_length(
            b"\x01\x02\x03", 3, "TEST_PACKET"
        )
        assert await PacketLengthValidator.validate_generic_min_length(b"\x01", 1, "SIMPLE_PACKET")

    @pytest.mark.asyncio
    async def test_validate_generic_min_length_invalid(self):
        """Testea validación genérica con longitud insuficiente."""
        assert not await PacketLengthValidator.validate_generic_min_length(
            b"\x01\x02", 3, "TEST_PACKET"
        )
        assert not await PacketLengthValidator.validate_generic_min_length(b"", 1, "EMPTY_PACKET")

    def test_get_packet_min_length(self):
        """Testea obtención de longitud mínima por packet_id."""
        assert PacketLengthValidator.get_packet_min_length(1) == 1  # THROW_DICES
        assert PacketLengthValidator.get_packet_min_length(6) == 2  # WALK
        assert PacketLengthValidator.get_packet_min_length(3) == 2  # DOUBLE_CLICK
        assert PacketLengthValidator.get_packet_min_length(19) == 3  # EQUIP_ITEM
        assert PacketLengthValidator.get_packet_min_length(26) == 3  # LEFT_CLICK
        assert PacketLengthValidator.get_packet_min_length(39) == 7  # CAST_SPELL (corregido a 7)

        # Packet no definido debe retornar 1 por defecto
        assert PacketLengthValidator.get_packet_min_length(999) == 1

    def test_is_packet_empty(self):
        """Testea detección de packets vacíos."""
        assert PacketLengthValidator.is_packet_empty(b"")
        assert not PacketLengthValidator.is_packet_empty(b"\x01")
        assert not PacketLengthValidator.is_packet_empty(b"\x01\x02\x03")

    def test_min_packet_lengths_completeness(self):
        """Verifica que todos los packet_ids definidos tengan longitud mínima."""
        defined_packets = set(PacketLengthValidator.MIN_PACKET_LENGTHS.keys())

        # Verificar que los packets básicos estén definidos
        basic_packets = {1, 6, 19, 26, 39}  # THROW_DICES, WALK, EQUIP_ITEM, LEFT_CLICK, CAST_SPELL
        assert basic_packets.issubset(defined_packets)

        # Verificar que todas las longitudes sean al menos 1 (PacketID)
        for packet_id, min_length in PacketLengthValidator.MIN_PACKET_LENGTHS.items():
            assert min_length >= 1, (
                f"Packet {packet_id} tiene longitud mínima inválida: {min_length}"
            )

    @pytest.mark.asyncio
    async def test_edge_cases(self):
        """Testea casos límite."""
        # Longitud exacta
        assert await PacketLengthValidator.validate_min_length(
            b"\x06\x01", 6
        )  # WALK con longitud exacta

        # Un byte extra
        assert await PacketLengthValidator.validate_min_length(b"\x06\x01\xff", 6)  # WALK con extra

        # Packet con datos no válidos pero longitud correcta
        assert await PacketLengthValidator.validate_min_length(
            b"\xff\xff\xff", 26
        )  # LEFT_CLICK con datos inválidos pero longitud ok
