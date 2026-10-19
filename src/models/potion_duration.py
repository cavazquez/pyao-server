"""Unidad canónica de pociones y conversión del contador del AO original."""

import math

from src.models.item_types import TipoPocion

LEGACY_TICK_SECONDS = 0.04
DEFAULT_DURATION_SECONDS = 40.0
MAX_DURATION_SECONDS = 86400.0


def normalize_potion_duration(data: dict[str, object]) -> dict[str, object]:
    """Normaliza una copia del dato; los contadores legacy representan ticks.

    Returns:
        Datos con EffectDurationSeconds para pociones de atributos.

    Raises:
        TypeError: Si el valor no es numérico.
        ValueError: Si la duración no es un número positivo finito y acotado.
    """
    if data.get("TipoPocion") not in {TipoPocion.AGILIDAD, TipoPocion.FUERZA}:
        return data
    value = data.get("EffectDurationSeconds")
    if value is None:
        legacy = data.get("DuracionEfecto", 1000)
        if isinstance(legacy, bool) or not isinstance(legacy, (int, float, str)):
            message = "DuracionEfecto debe ser un contador numérico"
            raise TypeError(message)
        value = float(legacy) * LEGACY_TICK_SECONDS
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        message = "EffectDurationSeconds debe ser numérico"
        raise TypeError(message)
    duration = float(value)
    if not math.isfinite(duration) or not 0 < duration <= MAX_DURATION_SECONDS:
        message = "EffectDurationSeconds debe estar entre 0 y 86400 segundos"
        raise ValueError(message)
    return {**data, "EffectDurationSeconds": duration}
