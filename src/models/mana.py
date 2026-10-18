"""Rango persistible del maná en el protocolo AO int16 con signo."""

MAX_MANA = 32767


def validate_mana(current: int, maximum: int = MAX_MANA) -> None:
    """Valida antes de persistir, sin ocultar una discrepancia al serializar.

    Raises:
        ValueError: Si el máximo o el actual exceden el protocolo o el presupuesto.
    """
    if not 0 <= current <= maximum <= MAX_MANA:
        msg = f"Maná fuera de rango: se requiere 0 <= actual <= máximo <= {MAX_MANA}"
        raise ValueError(msg)


def calculate_mana(intelligence: int, per_int: int, level: int = 1) -> int:
    """Satura el resultado de balance antes de guardarlo.

    Returns:
        Máximo de maná representable, entre cero y MAX_MANA.
    """
    return min(MAX_MANA, max(0, intelligence * per_int * level))
