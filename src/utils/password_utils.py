"""Utilidades para manejo seguro de contraseñas."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64_000,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Genera un hash Argon2id de la contraseña.

    Returns:
        str: Hash Argon2id que incluye salt y parámetros de costo.
    """
    return _PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica si una contraseña coincide con su hash Argon2id almacenado.

    Returns:
        bool: True si la contraseña es válida, False en caso contrario.
    """
    try:
        return _PASSWORD_HASHER.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
