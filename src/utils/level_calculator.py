"""Utilidades para calcular nivel y ELU (experiencia para subir de nivel).

Basado en la fórmula de Argentum Online VB6.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.config_manager import ConfigManager

logger = None  # Se inicializará si es necesario


def calculate_elu_for_level(level: int, config_manager: ConfigManager) -> int:
    """Calcula el ELU (experiencia necesaria) para alcanzar un nivel.

    Fórmula basada en Argentum Online VB6:
    ELU = base_elu * (level ^ exponent)

    Args:
        level: Nivel para el cual calcular el ELU.
        config_manager: ConfigManager para obtener configuración.

    Returns:
        ELU necesario para alcanzar el nivel especificado.
    """
    base_elu = config_manager.as_int("game.character.initial_elu", 300)
    # Exponente típico en AO: ~1.5-2.0, usando 1.8 como valor por defecto
    exponent = config_manager.as_float("game.character.elu_exponent", 1.8)

    if level <= 1:
        return base_elu

    elu = int(base_elu * (level**exponent))
    return max(elu, base_elu)  # Mínimo el ELU base


def calculate_total_exp_for_level(level: int, config_manager: ConfigManager) -> int:
    """Calcula la experiencia total acumulada necesaria para alcanzar un nivel.

    Suma todos los ELU de los niveles anteriores.

    Args:
        level: Nivel objetivo.
        config_manager: ConfigManager para obtener configuración.

    Returns:
        Experiencia total acumulada necesaria para alcanzar el nivel.
    """
    if level <= 1:
        return 0

    total_exp = 0
    for lvl in range(1, level):
        total_exp += calculate_elu_for_level(lvl, config_manager)

    return total_exp


def calculate_level_from_experience(total_experience: int, config_manager: ConfigManager) -> int:
    """Calcula el nivel actual basado en la experiencia total acumulada.

    Args:
        total_experience: Experiencia total acumulada del jugador.
        config_manager: ConfigManager para obtener configuración.

    Returns:
        Nivel calculado basado en la experiencia.
    """
    if total_experience <= 0:
        return 1

    level = 1
    accumulated_exp = 0

    # Iterar hasta encontrar el nivel máximo alcanzable
    while True:
        elu_for_next_level = calculate_elu_for_level(level, config_manager)
        if accumulated_exp + elu_for_next_level > total_experience:
            break
        accumulated_exp += elu_for_next_level
        level += 1

        # Límite de seguridad (nivel máximo 255)
        max_level = 255
        if level >= max_level:
            break

    return level


def calculate_remaining_elu(
    total_experience: int, current_level: int, config_manager: ConfigManager
) -> int:
    """Calcula el ELU restante para el siguiente nivel.

    Args:
        total_experience: Experiencia total acumulada del jugador.
        current_level: Nivel actual del jugador.
        config_manager: ConfigManager para obtener configuración.

    Returns:
        ELU restante para alcanzar el siguiente nivel.
    """
    # Calcular experiencia total necesaria para el nivel actual
    calculate_total_exp_for_level(current_level, config_manager)

    # Calcular experiencia necesaria para el siguiente nivel
    exp_for_next_level = calculate_total_exp_for_level(current_level + 1, config_manager)

    # ELU restante = experiencia necesaria para siguiente nivel - experiencia actual
    remaining = exp_for_next_level - total_experience

    return max(remaining, 0)
