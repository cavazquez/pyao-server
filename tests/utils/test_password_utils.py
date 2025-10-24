"""Tests para password_utils."""

from src.utils.password_utils import hash_password, verify_password


def test_hash_password_generates_argon2_hash() -> None:
    """Verifica que hash_password genere un hash Argon2id válido."""
    password = "test_password_123"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert password not in hashed


def test_hash_password_uses_random_salt() -> None:
    """Verifica que la misma contraseña genere hashes distintos (salt aleatorio)."""
    password = "same_password"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 != hash2


def test_hash_password_different_for_different_passwords() -> None:
    """Verifica que contraseñas diferentes generen hashes diferentes."""
    password1 = "password1"
    password2 = "password2"

    hash1 = hash_password(password1)
    hash2 = hash_password(password2)

    assert hash1 != hash2


def test_hash_password_case_sensitive() -> None:
    """Verifica que el hash sea sensible a mayúsculas/minúsculas."""
    password_lower = "password"
    password_upper = "PASSWORD"

    hash_lower = hash_password(password_lower)
    hash_upper = hash_password(password_upper)

    assert hash_lower != hash_upper


def test_verify_password_correct() -> None:
    """Verifica que verify_password funcione con contraseña correcta."""
    password = "correct_password"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect() -> None:
    """Verifica que verify_password rechace contraseña incorrecta."""
    password = "correct_password"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_verify_password_case_sensitive() -> None:
    """Verifica que verify_password sea sensible a mayúsculas/minúsculas."""
    password = "Password123"
    hashed = hash_password(password)

    assert verify_password("password123", hashed) is False
    assert verify_password("PASSWORD123", hashed) is False
    assert verify_password("Password123", hashed) is True


def test_verify_password_invalid_hash_returns_false() -> None:
    """Verifica que verify_password maneje hashes inválidos."""
    assert verify_password("password", "not_a_valid_hash") is False


def test_hash_password_empty_string() -> None:
    """Verifica que se pueda hashear una cadena vacía."""
    password = ""
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password("", hashed) is True


def test_hash_password_unicode() -> None:
    """Verifica que se puedan hashear contraseñas con caracteres Unicode."""
    password = "contraseña_española_🔒"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True


def test_hash_password_special_characters() -> None:
    """Verifica que se puedan hashear contraseñas con caracteres especiales."""
    password = "p@ssw0rd!#$%^&*()"
    hashed = hash_password(password)

    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
