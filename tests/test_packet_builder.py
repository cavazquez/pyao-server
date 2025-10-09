"""Tests para el constructor de paquetes."""

import pytest

from src.packet_builder import PacketBuilder


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
