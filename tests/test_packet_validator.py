"""Tests para PacketValidator."""

import struct

from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator, ValidationResult


def test_packet_validator_read_slot_valid() -> None:
    """Verifica que read_slot valida slots correctos."""
    data = bytes([1, 5])  # PacketID + slot=5
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    slot = validator.read_slot(min_slot=1, max_slot=20)

    assert slot == 5
    assert not validator.has_errors()


def test_packet_validator_read_slot_invalid_too_low() -> None:
    """Verifica que read_slot rechaza slots muy bajos."""
    data = bytes([1, 0])  # PacketID + slot=0
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    slot = validator.read_slot(min_slot=1, max_slot=20)

    assert slot is None
    assert validator.has_errors()
    assert "Slot inválido" in validator.get_error_message()


def test_packet_validator_read_slot_invalid_too_high() -> None:
    """Verifica que read_slot rechaza slots muy altos."""
    data = bytes([1, 25])  # PacketID + slot=25
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    slot = validator.read_slot(min_slot=1, max_slot=20)

    assert slot is None
    assert validator.has_errors()
    assert "Slot inválido" in validator.get_error_message()


def test_packet_validator_read_quantity_valid() -> None:
    """Verifica que read_quantity valida cantidades correctas."""
    data = bytes([1]) + struct.pack("<H", 100)  # PacketID + quantity=100
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    quantity = validator.read_quantity(min_qty=1, max_qty=10000)

    assert quantity == 100
    assert not validator.has_errors()


def test_packet_validator_read_quantity_invalid_too_low() -> None:
    """Verifica que read_quantity rechaza cantidades muy bajas."""
    data = bytes([1]) + struct.pack("<H", 0)  # PacketID + quantity=0
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    quantity = validator.read_quantity(min_qty=1, max_qty=10000)

    assert quantity is None
    assert validator.has_errors()
    assert "Cantidad inválida" in validator.get_error_message()


def test_packet_validator_read_quantity_invalid_too_high() -> None:
    """Verifica que read_quantity rechaza cantidades muy altas."""
    data = bytes([1]) + struct.pack("<H", 15000)  # PacketID + quantity=15000
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    quantity = validator.read_quantity(min_qty=1, max_qty=10000)

    assert quantity is None
    assert validator.has_errors()
    assert "Cantidad inválida" in validator.get_error_message()


def test_packet_validator_read_username_valid() -> None:
    """Verifica que read_username valida usernames correctos."""
    username = "TestUser"
    username_bytes = username.encode("utf-16-le")
    length = len(username_bytes)
    data = bytes([1]) + struct.pack("<H", length) + username_bytes
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.read_username(max_length=20)

    assert result == username
    assert not validator.has_errors()


def test_packet_validator_read_username_empty() -> None:
    """Verifica que read_username rechaza usernames vacíos."""
    data = bytes([1]) + struct.pack("<H", 0)  # PacketID + empty string
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.read_username(max_length=20)

    assert result is None
    assert validator.has_errors()
    assert "Username vacío" in validator.get_error_message()


def test_packet_validator_read_username_too_long() -> None:
    """Verifica que read_username rechaza usernames muy largos."""
    username = "A" * 30
    username_bytes = username.encode("utf-16-le")
    length = len(username_bytes)
    data = bytes([1]) + struct.pack("<H", length) + username_bytes
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.read_username(max_length=20)

    assert result is None
    assert validator.has_errors()
    assert "Username muy largo" in validator.get_error_message()


def test_packet_validator_read_coordinates_valid() -> None:
    """Verifica que read_coordinates valida coordenadas correctas."""
    data = bytes([1, 50, 75])  # PacketID + x=50, y=75
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    coords = validator.read_coordinates(max_x=100, max_y=100)

    assert coords == (50, 75)
    assert not validator.has_errors()


def test_packet_validator_read_coordinates_invalid() -> None:
    """Verifica que read_coordinates rechaza coordenadas inválidas."""
    data = bytes([1, 0, 101])  # PacketID + x=0, y=101 (fuera de rango)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    coords = validator.read_coordinates(max_x=100, max_y=100)

    assert coords is None
    assert validator.has_errors()
    assert "Coordenadas inválidas" in validator.get_error_message()


def test_packet_validator_read_password_valid() -> None:
    """Verifica que read_password valida contraseñas correctas."""
    password = "SecurePass123"
    password_bytes = password.encode("utf-16-le")
    length = len(password_bytes)
    data = bytes([1]) + struct.pack("<H", length) + password_bytes
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.read_password(min_length=6, max_length=32)

    assert result == password
    assert not validator.has_errors()


def test_packet_validator_read_password_too_short() -> None:
    """Verifica que read_password rechaza contraseñas muy cortas."""
    password = "123"
    password_bytes = password.encode("utf-16-le")
    length = len(password_bytes)
    data = bytes([1]) + struct.pack("<H", length) + password_bytes
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.read_password(min_length=6, max_length=32)

    assert result is None
    assert validator.has_errors()
    assert "Contraseña muy corta" in validator.get_error_message()


def test_packet_validator_read_password_too_long() -> None:
    """Verifica que read_password rechaza contraseñas muy largas."""
    password = "A" * 50
    password_bytes = password.encode("utf-16-le")
    length = len(password_bytes)
    data = bytes([1]) + struct.pack("<H", length) + password_bytes
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.read_password(min_length=6, max_length=32)

    assert result is None
    assert validator.has_errors()
    assert "Contraseña muy larga" in validator.get_error_message()


def test_packet_validator_read_spell_slot_valid() -> None:
    """Verifica que read_spell_slot valida slots de hechizo correctos."""
    data = bytes([1, 10])  # PacketID + spell_slot=10
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    slot = validator.read_spell_slot(max_slot=35)

    assert slot == 10
    assert not validator.has_errors()


def test_packet_validator_multiple_errors() -> None:
    """Verifica que el validador acumula múltiples errores."""
    data = bytes([1, 0]) + struct.pack("<H", 0)  # PacketID + slot=0, quantity=0
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    slot = validator.read_slot(min_slot=1, max_slot=20)
    quantity = validator.read_quantity(min_qty=1, max_qty=10000)

    assert slot is None
    assert quantity is None
    assert validator.has_errors()
    errors = validator.get_all_errors()
    assert len(errors) == 2
    assert "Slot inválido" in errors[0]
    assert "Cantidad inválida" in errors[1]


def test_packet_validator_clear_errors() -> None:
    """Verifica que clear_errors limpia los errores."""
    data = bytes([1, 0])  # PacketID + slot=0 (inválido)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    validator.read_slot(min_slot=1, max_slot=20)
    assert validator.has_errors()

    validator.clear_errors()
    assert not validator.has_errors()


def test_validation_result_success() -> None:
    """Verifica que ValidationResult funciona con éxito."""
    result: ValidationResult[int] = ValidationResult(success=True, data=42)

    assert result.success
    assert result.data == 42
    assert result.error_message is None


def test_validation_result_failure() -> None:
    """Verifica que ValidationResult funciona con error."""
    result: ValidationResult[int] = ValidationResult(
        success=False, error_message="Error de validación"
    )

    assert not result.success
    assert result.data is None
    assert result.error_message == "Error de validación"
