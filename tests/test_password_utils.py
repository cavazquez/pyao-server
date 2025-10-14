"""Tests para password_utils."""

from src.password_utils import hash_password, verify_password


def test_hash_password_generates_sha256():
    """Verifica que hash_password genere un hash SHA-256 válido."""
    password = "test_password_123"
    hashed = hash_password(password)

    # SHA-256 genera un hash hexadecimal de 64 caracteres
    assert len(hashed) == 64
    assert all(c in "0123456789abcdef" for c in hashed)


def test_hash_password_is_deterministic():
    """Verifica que la misma contraseña siempre genere el mismo hash."""
    password = "same_password"
    hash1 = hash_password(password)
    hash2 = hash_password(password)

    assert hash1 == hash2


def test_hash_password_different_for_different_passwords():
    """Verifica que contraseñas diferentes generen hashes diferentes."""
    password1 = "password1"
    password2 = "password2"

    hash1 = hash_password(password1)
    hash2 = hash_password(password2)

    assert hash1 != hash2


def test_hash_password_case_sensitive():
    """Verifica que el hash sea sensible a mayúsculas/minúsculas."""
    password_lower = "password"
    password_upper = "PASSWORD"

    hash_lower = hash_password(password_lower)
    hash_upper = hash_password(password_upper)

    assert hash_lower != hash_upper


def test_verify_password_correct():
    """Verifica que verify_password funcione con contraseña correcta."""
    password = "correct_password"
    hashed = hash_password(password)

    assert verify_password(password, hashed) is True


def test_verify_password_incorrect():
    """Verifica que verify_password rechace contraseña incorrecta."""
    password = "correct_password"
    wrong_password = "wrong_password"
    hashed = hash_password(password)

    assert verify_password(wrong_password, hashed) is False


def test_verify_password_case_sensitive():
    """Verifica que verify_password sea sensible a mayúsculas/minúsculas."""
    password = "Password123"
    hashed = hash_password(password)

    assert verify_password("password123", hashed) is False
    assert verify_password("PASSWORD123", hashed) is False
    assert verify_password("Password123", hashed) is True


def test_hash_password_empty_string():
    """Verifica que se pueda hashear una cadena vacía."""
    password = ""
    hashed = hash_password(password)

    assert len(hashed) == 64
    assert verify_password("", hashed) is True


def test_hash_password_unicode():
    """Verifica que se puedan hashear contraseñas con caracteres Unicode."""
    password = "contraseña_española_🔒"
    hashed = hash_password(password)

    assert len(hashed) == 64
    assert verify_password(password, hashed) is True


def test_hash_password_special_characters():
    """Verifica que se puedan hashear contraseñas con caracteres especiales."""
    password = "p@ssw0rd!#$%^&*()"
    hashed = hash_password(password)

    assert len(hashed) == 64
    assert verify_password(password, hashed) is True
