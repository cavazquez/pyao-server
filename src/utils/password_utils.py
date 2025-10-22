"""Utilidades para manejo seguro de contraseñas."""

import hashlib


def hash_password(password: str) -> str:
    """Genera un hash SHA-256 de la contraseña.

    Args:
        password: Contraseña en texto plano.

    Returns:
        Hash hexadecimal de la contraseña.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    """Verifica si una contraseña coincide con su hash.

    Args:
        password: Contraseña en texto plano a verificar.
        password_hash: Hash almacenado de la contraseña.

    Returns:
        True si la contraseña coincide con el hash, False en caso contrario.
    """
    return hash_password(password) == password_hash
