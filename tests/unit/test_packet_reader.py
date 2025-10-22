"""Tests para PacketReader."""

import struct

import pytest

from src.network.packet_reader import PacketReader


def test_packet_reader_read_byte() -> None:
    """Verifica que PacketReader lee bytes correctamente."""
    # Packet: [PacketID=1][Byte=42]
    data = bytes([1, 42])
    reader = PacketReader(data)

    value = reader.read_byte()

    assert value == 42
    assert reader.offset == 2


def test_packet_reader_read_int16() -> None:
    """Verifica que PacketReader lee int16 little-endian correctamente."""
    # Packet: [PacketID=1][Int16=1000]
    data = bytes([1]) + struct.pack("<H", 1000)
    reader = PacketReader(data)

    value = reader.read_int16()

    assert value == 1000
    assert reader.offset == 3


def test_packet_reader_read_int32() -> None:
    """Verifica que PacketReader lee int32 little-endian correctamente."""
    # Packet: [PacketID=1][Int32=100000]
    data = bytes([1]) + struct.pack("<I", 100000)
    reader = PacketReader(data)

    value = reader.read_int32()

    assert value == 100000
    assert reader.offset == 5


def test_packet_reader_read_string() -> None:
    """Verifica que PacketReader lee strings UTF-16LE correctamente."""
    # Packet: [PacketID=1][Length=10][String="Hola" en UTF-16LE]
    text = "Hola"
    text_bytes = text.encode("utf-16-le")
    length = len(text_bytes)
    data = bytes([1]) + struct.pack("<H", length) + text_bytes
    reader = PacketReader(data)

    value = reader.read_string()

    assert value == "Hola"
    assert reader.offset == 1 + 2 + length


def test_packet_reader_read_multiple_values() -> None:
    """Verifica que PacketReader lee múltiples valores secuencialmente."""
    # Packet: [PacketID=1][Byte=5][Int16=100][Int32=50000]
    data = bytes([1, 5]) + struct.pack("<H", 100) + struct.pack("<I", 50000)
    reader = PacketReader(data)

    byte_val = reader.read_byte()
    int16_val = reader.read_int16()
    int32_val = reader.read_int32()

    assert byte_val == 5
    assert int16_val == 100
    assert int32_val == 50000


def test_packet_reader_remaining_bytes() -> None:
    """Verifica que remaining_bytes retorna la cantidad correcta."""
    data = bytes([1, 2, 3, 4, 5])
    reader = PacketReader(data)

    assert reader.remaining_bytes() == 4  # 5 bytes - 1 (PacketID)

    reader.read_byte()
    assert reader.remaining_bytes() == 3

    reader.read_byte()
    assert reader.remaining_bytes() == 2


def test_packet_reader_has_more_data() -> None:
    """Verifica que has_more_data funciona correctamente."""
    data = bytes([1, 2, 3])
    reader = PacketReader(data)

    assert reader.has_more_data() is True

    reader.read_byte()
    assert reader.has_more_data() is True

    reader.read_byte()
    assert reader.has_more_data() is False


def test_packet_reader_reset() -> None:
    """Verifica que reset() reinicia el offset."""
    data = bytes([1, 2, 3, 4])
    reader = PacketReader(data)

    reader.read_byte()
    reader.read_byte()
    assert reader.offset == 3

    reader.reset()
    assert reader.offset == 1

    # Debe poder leer de nuevo desde el inicio
    value = reader.read_byte()
    assert value == 2


def test_packet_reader_get_packet_id() -> None:
    """Verifica que get_packet_id retorna el PacketID correctamente."""
    data = bytes([42, 1, 2, 3])
    reader = PacketReader(data)

    packet_id = reader.get_packet_id()

    assert packet_id == 42
    assert reader.offset == 1  # No debe mover el offset


def test_packet_reader_get_packet_id_empty_data() -> None:
    """Verifica que get_packet_id maneja datos vacíos."""
    data = bytes([])
    reader = PacketReader(data)

    packet_id = reader.get_packet_id()

    assert packet_id == 0


def test_packet_reader_read_beyond_data_raises_error() -> None:
    """Verifica que leer más allá de los datos disponibles lanza error."""
    data = bytes([1, 2])  # Solo 1 byte de datos después del PacketID
    reader = PacketReader(data)

    reader.read_byte()  # OK

    with pytest.raises(struct.error):
        reader.read_byte()  # Error: no hay más datos


def test_packet_reader_read_int16_insufficient_data() -> None:
    """Verifica que leer int16 sin suficientes datos lanza error."""
    data = bytes([1, 2])  # Solo 1 byte después del PacketID
    reader = PacketReader(data)

    with pytest.raises(struct.error):
        reader.read_int16()  # Error: necesita 2 bytes


def test_packet_reader_read_string_with_special_characters() -> None:
    """Verifica que PacketReader lee strings con caracteres especiales."""
    text = "Hola! ñáéíóú 你好"
    text_bytes = text.encode("utf-16-le")
    length = len(text_bytes)
    data = bytes([1]) + struct.pack("<H", length) + text_bytes
    reader = PacketReader(data)

    value = reader.read_string()

    assert value == text


def test_packet_reader_read_empty_string() -> None:
    """Verifica que PacketReader lee strings vacíos correctamente."""
    data = bytes([1]) + struct.pack("<H", 0)  # Length = 0
    reader = PacketReader(data)

    value = reader.read_string()

    assert not value  # Empty string
    assert reader.offset == 3  # PacketID + 2 bytes de length


def test_packet_reader_complex_packet() -> None:
    """Verifica lectura de un packet complejo con múltiples tipos."""
    # Simular packet de comercio: [PacketID][slot:byte][quantity:int16][price:int32]
    slot = 5
    quantity = 100
    price = 50000

    data = bytes([1, slot]) + struct.pack("<H", quantity) + struct.pack("<I", price)
    reader = PacketReader(data)

    read_slot = reader.read_byte()
    read_quantity = reader.read_int16()
    read_price = reader.read_int32()

    assert read_slot == slot
    assert read_quantity == quantity
    assert read_price == price
    assert not reader.has_more_data()
