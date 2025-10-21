"""Tests para los métodos validate_* completos del PacketValidator."""

import struct

from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator


def test_validate_walk_packet_success() -> None:
    """Verifica que validate_walk_packet retorna éxito con heading válido."""
    # Packet WALK con heading=1 (Norte)
    data = bytes([6, 1])  # PacketID=6 (WALK), heading=1
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_walk_packet()

    assert result.success is True
    assert result.data == {"heading": 1}
    assert result.error_message is None


def test_validate_walk_packet_invalid_heading() -> None:
    """Verifica que validate_walk_packet retorna error con heading inválido."""
    # Packet WALK con heading=5 (inválido, debe ser 1-4)
    data = bytes([6, 5])  # PacketID=6 (WALK), heading=5
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_walk_packet()

    assert result.success is False
    assert result.data is None
    assert result.error_message is not None
    assert "Dirección inválida" in result.error_message


def test_validate_attack_packet_success() -> None:
    """Verifica que validate_attack_packet valida correctamente un packet ATTACK válido.
    
    Nota: El packet ATTACK no tiene parámetros. El jugador ataca en la dirección
    que está mirando (según su heading).
    """
    # Packet ATTACK (solo PacketID, sin datos adicionales)
    data = bytes([8])  # PacketID=8 (ATTACK)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_attack_packet()

    assert result.success is True
    assert result.data == {}  # No hay datos, solo PacketID
    assert result.error_message is None


def test_validate_attack_packet_minimal() -> None:
    """Verifica que validate_attack_packet acepta packet mínimo (solo PacketID)."""
    # Packet ATTACK mínimo (solo PacketID)
    data = bytes([8])  # PacketID=8 (ATTACK)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_attack_packet()

    # El packet es válido incluso con solo el PacketID
    assert result.success is True
    assert result.data == {}
    assert result.error_message is None


def test_validate_login_packet_success() -> None:
    """Verifica que validate_login_packet retorna éxito con credenciales válidas."""
    # Packet LOGIN con username="testuser" y password="password123"
    username = "testuser"
    password = "password123"

    # Construir packet: PacketID + length(username) + username + length(password) + password
    username_bytes = username.encode("utf-8")
    password_bytes = password.encode("utf-8")

    data = (
        bytes([2])  # PacketID=2 (LOGIN)
        + struct.pack("<H", len(username_bytes))
        + username_bytes
        + struct.pack("<H", len(password_bytes))
        + password_bytes
    )

    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_login_packet()

    assert result.success is True
    assert result.data == {"username": username, "password": password}
    assert result.error_message is None


def test_validate_login_packet_username_too_short() -> None:
    """Verifica que validate_login_packet retorna error con username muy corto."""
    # Packet LOGIN con username="ab" (muy corto, mínimo 3)
    username = "ab"
    password = "password123"

    username_bytes = username.encode("utf-8")
    password_bytes = password.encode("utf-8")

    data = (
        bytes([2])
        + struct.pack("<H", len(username_bytes))
        + username_bytes
        + struct.pack("<H", len(password_bytes))
        + password_bytes
    )

    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_login_packet()

    assert result.success is False
    assert result.data is None
    assert result.error_message is not None
    assert "muy corto" in result.error_message.lower()


def test_validate_login_packet_password_too_short() -> None:
    """Verifica que validate_login_packet retorna error con password muy corta."""
    # Packet LOGIN con password="12345" (muy corta, mínimo 6)
    username = "testuser"
    password = "12345"

    username_bytes = username.encode("utf-8")
    password_bytes = password.encode("utf-8")

    data = (
        bytes([2])
        + struct.pack("<H", len(username_bytes))
        + username_bytes
        + struct.pack("<H", len(password_bytes))
        + password_bytes
    )

    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_login_packet()

    assert result.success is False
    assert result.data is None
    assert result.error_message is not None
    assert "muy cort" in result.error_message.lower()


def test_validate_cast_spell_packet_success() -> None:
    """Verifica que validate_cast_spell_packet retorna éxito con slot válido."""
    # Packet CAST_SPELL con spell_slot=5
    data = bytes([13, 5])  # PacketID=13 (CAST_SPELL), spell_slot=5
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_cast_spell_packet()

    assert result.success is True
    assert result.data == {"spell_slot": 5}
    assert result.error_message is None


def test_validate_cast_spell_packet_invalid_slot() -> None:
    """Verifica que validate_cast_spell_packet retorna error con slot inválido."""
    # Packet CAST_SPELL con spell_slot=40 (inválido, máximo 35)
    data = bytes([13, 40])  # PacketID=13, spell_slot=40
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_cast_spell_packet()

    assert result.success is False
    assert result.data is None
    assert result.error_message is not None
    assert "Slot inválido" in result.error_message


def test_validate_drop_packet_success() -> None:
    """Verifica que validate_drop_packet retorna éxito con datos válidos."""
    # Packet DROP con slot=5, quantity=10
    data = bytes([18, 5]) + struct.pack("<H", 10)  # PacketID=18, slot=5, quantity=10
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_drop_packet()

    assert result.success is True
    assert result.data == {"slot": 5, "quantity": 10}
    assert result.error_message is None


def test_validate_drop_packet_invalid_slot() -> None:
    """Verifica que validate_drop_packet retorna error con slot inválido."""
    # Packet DROP con slot=25 (inválido, máximo 20)
    data = bytes([18, 25]) + struct.pack("<H", 10)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_drop_packet()

    assert result.success is False
    assert result.data is None
    assert result.error_message is not None
    assert "Slot inválido" in result.error_message


def test_validate_drop_packet_invalid_quantity() -> None:
    """Verifica que validate_drop_packet retorna error con cantidad inválida."""
    # Packet DROP con quantity=0 (inválido, mínimo 1)
    data = bytes([18, 5]) + struct.pack("<H", 0)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_drop_packet()

    assert result.success is False
    assert result.data is None
    assert result.error_message is not None
    assert "Cantidad inválida" in result.error_message


def test_validate_pickup_packet_success() -> None:
    """Verifica que validate_pickup_packet retorna éxito."""
    # Packet PICK_UP (sin parámetros adicionales)
    data = bytes([19])  # PacketID=19 (PICK_UP)
    reader = PacketReader(data)
    validator = PacketValidator(reader)

    result = validator.validate_pickup_packet()

    assert result.success is True
    assert result.data == {}
    assert result.error_message is None


def test_validation_result_log_validation_success() -> None:
    """Verifica que log_validation registra éxito correctamente."""
    # Crear resultado exitoso
    data = bytes([6, 1])
    reader = PacketReader(data)
    validator = PacketValidator(reader)
    result = validator.validate_walk_packet()

    # Llamar a log_validation (no lanza excepción)
    result.log_validation("WALK", 6, "127.0.0.1:12345")

    # Si llegamos aquí, el método funcionó correctamente
    assert result.success is True


def test_validation_result_log_validation_failure() -> None:
    """Verifica que log_validation registra error correctamente."""
    # Crear resultado fallido
    data = bytes([6, 5])  # heading inválido
    reader = PacketReader(data)
    validator = PacketValidator(reader)
    result = validator.validate_walk_packet()

    # Llamar a log_validation (no lanza excepción)
    result.log_validation("WALK", 6, "127.0.0.1:12345")

    # Si llegamos aquí, el método funcionó correctamente
    assert result.success is False
