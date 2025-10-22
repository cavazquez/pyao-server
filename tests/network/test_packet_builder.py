"""Tests para el constructor de paquetes."""

import pytest

from src.network.packet_builder import PacketBuilder


def test_packet_builder_empty() -> None:
    """Verifica que un paquete vacío tenga longitud 0."""
    packet = PacketBuilder()
    assert len(packet) == 0
    assert packet.to_bytes() == b""


def test_packet_builder_add_single_byte() -> None:
    """Verifica que se pueda agregar un byte."""
    packet = PacketBuilder()
    packet.add_byte(42)

    assert len(packet) == 1
    assert packet.to_bytes() == bytes([42])


def test_packet_builder_add_multiple_bytes() -> None:
    """Verifica que se puedan agregar múltiples bytes."""
    packet = PacketBuilder()
    packet.add_byte(1)
    packet.add_byte(2)
    packet.add_byte(3)

    assert len(packet) == 3
    assert packet.to_bytes() == bytes([1, 2, 3])


def test_packet_builder_chaining() -> None:
    """Verifica que se puedan encadenar llamadas a add_byte."""
    packet = PacketBuilder()
    result = packet.add_byte(10).add_byte(20).add_byte(30)

    assert result is packet  # Verifica que retorna self
    assert len(packet) == 3
    assert packet.to_bytes() == bytes([10, 20, 30])


def test_packet_builder_min_max_values() -> None:
    """Verifica que funcione con valores mínimos y máximos de byte."""
    packet = PacketBuilder()
    packet.add_byte(0)
    packet.add_byte(255)

    assert len(packet) == 2
    assert packet.to_bytes() == bytes([0, 255])


def test_packet_builder_to_bytes_multiple_calls() -> None:
    """Verifica que to_bytes() se pueda llamar múltiples veces."""
    packet = PacketBuilder()
    packet.add_byte(1).add_byte(2).add_byte(3)

    # Llamar to_bytes() varias veces debe retornar lo mismo
    result1 = packet.to_bytes()
    result2 = packet.to_bytes()

    assert result1 == result2
    assert result1 == bytes([1, 2, 3])


@pytest.mark.parametrize(
    "values",
    [
        [1, 2, 3, 4, 5],
        [255, 0, 128, 64, 32],
        [10],
        list(range(256)),  # Todos los valores posibles de byte
    ],
)
def test_packet_builder_parametrized(values: list[int]) -> None:
    """Test parametrizado con diferentes secuencias de bytes."""
    packet = PacketBuilder()
    for value in values:
        packet.add_byte(value)

    assert len(packet) == len(values)
    assert packet.to_bytes() == bytes(values)


def test_packet_builder_realistic_packet() -> None:
    """Verifica construcción de un paquete realista (similar a DiceRoll)."""
    packet = PacketBuilder()
    packet.add_byte(67)  # PacketID
    packet.add_byte(15)  # Strength
    packet.add_byte(12)  # Agility
    packet.add_byte(14)  # Intelligence
    packet.add_byte(10)  # Charisma
    packet.add_byte(16)  # Constitution

    result = packet.to_bytes()
    assert len(result) == 6
    assert result[0] == 67
    assert result[1] == 15
    assert result[2] == 12
    assert result[3] == 14
    assert result[4] == 10
    assert result[5] == 16


def test_packet_builder_add_byte_validation_too_large() -> None:
    """Verifica que add_byte rechace valores mayores a 255."""
    packet = PacketBuilder()

    with pytest.raises(ValueError, match="must be in range 0-255"):
        packet.add_byte(256)


def test_packet_builder_add_byte_validation_negative() -> None:
    """Verifica que add_byte rechace valores negativos."""
    packet = PacketBuilder()

    with pytest.raises(ValueError, match="must be in range 0-255"):
        packet.add_byte(-1)


def test_packet_builder_add_string_utf8() -> None:
    """Verifica que add_string agregue texto con codificación UTF-8."""
    packet = PacketBuilder()
    packet.add_string("Hello")

    result = packet.to_bytes()
    assert result == b"Hello"


def test_packet_builder_add_string_with_encoding() -> None:
    """Verifica que add_string funcione con diferentes codificaciones."""
    packet = PacketBuilder()
    packet.add_string("Hola", encoding="ascii")

    result = packet.to_bytes()
    assert result == b"Hola"


def test_packet_builder_add_string_unicode() -> None:
    """Verifica que add_string maneje caracteres Unicode."""
    packet = PacketBuilder()
    packet.add_string("Español: ñ, á, é")

    result = packet.to_bytes()
    assert result == "Español: ñ, á, é".encode()


def test_packet_builder_add_bytes() -> None:
    """Verifica que add_bytes agregue bytes directamente."""
    packet = PacketBuilder()
    packet.add_bytes(b"\x01\x02\x03")

    result = packet.to_bytes()
    assert result == b"\x01\x02\x03"


def test_packet_builder_mixed_operations() -> None:
    """Verifica que se puedan mezclar diferentes tipos de operaciones."""
    packet = PacketBuilder()
    packet.add_byte(1)
    packet.add_string("AB")
    packet.add_byte(2)
    packet.add_bytes(b"\x03\x04")

    result = packet.to_bytes()
    # Byte 1, then "AB" as ASCII (65, 66), then bytes 2, 3, 4
    expected = bytes([1, 65, 66, 2, 3, 4])
    assert result == expected


def test_packet_builder_chaining_all_methods() -> None:
    """Verifica encadenamiento con todos los métodos."""
    packet = PacketBuilder()
    result = packet.add_byte(1).add_string("X").add_bytes(b"\x02").add_byte(3)

    assert result is packet
    assert packet.to_bytes() == bytes([1, 88, 2, 3])  # 88 = 'X'


def test_packet_builder_add_int16_positive() -> None:
    """Verifica que add_int16 agregue un entero de 16 bits positivo."""
    packet = PacketBuilder()
    packet.add_int16(1000)

    result = packet.to_bytes()
    # 1000 en little-endian: 0xE8 0x03
    assert len(result) == 2
    assert result == bytes([0xE8, 0x03])


def test_packet_builder_add_int16_negative() -> None:
    """Verifica que add_int16 maneje enteros negativos."""
    packet = PacketBuilder()
    packet.add_int16(-1000)

    result = packet.to_bytes()
    # -1000 en little-endian signed: 0x18 0xFC
    assert len(result) == 2
    assert result == bytes([0x18, 0xFC])


def test_packet_builder_add_int16_zero() -> None:
    """Verifica que add_int16 maneje el valor cero."""
    packet = PacketBuilder()
    packet.add_int16(0)

    result = packet.to_bytes()
    assert len(result) == 2
    assert result == bytes([0x00, 0x00])


def test_packet_builder_add_int16_max_min() -> None:
    """Verifica que add_int16 maneje valores máximos y mínimos."""
    packet = PacketBuilder()
    packet.add_int16(32767)  # Max int16
    packet.add_int16(-32768)  # Min int16

    result = packet.to_bytes()
    assert len(result) == 4
    # 32767 = 0xFF7F, -32768 = 0x0080 en little-endian
    assert result == bytes([0xFF, 0x7F, 0x00, 0x80])


def test_packet_builder_add_int32_positive() -> None:
    """Verifica que add_int32 agregue un entero de 32 bits positivo."""
    packet = PacketBuilder()
    packet.add_int32(100000)

    result = packet.to_bytes()
    # 100000 en little-endian: 0xA0 0x86 0x01 0x00
    assert len(result) == 4
    assert result == bytes([0xA0, 0x86, 0x01, 0x00])


def test_packet_builder_add_int32_negative() -> None:
    """Verifica que add_int32 maneje enteros negativos."""
    packet = PacketBuilder()
    packet.add_int32(-100000)

    result = packet.to_bytes()
    # -100000 en little-endian signed
    assert len(result) == 4
    assert result == bytes([0x60, 0x79, 0xFE, 0xFF])


def test_packet_builder_add_int32_zero() -> None:
    """Verifica que add_int32 maneje el valor cero."""
    packet = PacketBuilder()
    packet.add_int32(0)

    result = packet.to_bytes()
    assert len(result) == 4
    assert result == bytes([0x00, 0x00, 0x00, 0x00])


def test_packet_builder_mixed_with_integers() -> None:
    """Verifica que se puedan mezclar bytes e integers."""
    packet = PacketBuilder()
    packet.add_byte(1)
    packet.add_int16(256)
    packet.add_int32(65536)
    packet.add_byte(2)

    result = packet.to_bytes()
    # Byte 1, int16(256)=[0x00,0x01], int32(65536)=[0x00,0x00,0x01,0x00], Byte 2
    expected = bytes([1, 0x00, 0x01, 0x00, 0x00, 0x01, 0x00, 2])
    assert len(result) == 8
    assert result == expected


def test_packet_builder_chaining_with_integers() -> None:
    """Verifica encadenamiento con los métodos de enteros."""
    packet = PacketBuilder()
    result = packet.add_byte(1).add_int16(100).add_int32(1000).add_byte(2)

    assert result is packet
    # Byte 1, int16(100)=[0x64,0x00], int32(1000)=[0xE8,0x03,0x00,0x00], Byte 2
    expected = bytes([1, 0x64, 0x00, 0xE8, 0x03, 0x00, 0x00, 2])
    assert packet.to_bytes() == expected
