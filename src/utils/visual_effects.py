"""Constantes para efectos visuales (FX) del juego."""

from enum import IntEnum


class VisualEffectID(IntEnum):
    """IDs de efectos visuales del cliente Argentum Online.

    Estos IDs corresponden a los efectos gráficos que se muestran en el cliente.
    Los valores están basados en el cliente original de VB6.
    """

    # Efectos de spawn/aparición
    SPAWN_BLUE = 1  # Efecto azul de aparición
    SPAWN_RED = 2  # Efecto rojo de aparición
    SPAWN_YELLOW = 3  # Efecto amarillo de aparición (común para login)
    SPAWN_GREEN = 4  # Efecto verde de aparición

    # Efectos de magia
    FIREBALL = 5  # Bola de fuego
    LIGHTNING = 6  # Rayo
    HEAL = 7  # Curación
    POISON = 8  # Veneno

    # Efectos de combate
    BLOOD = 10  # Sangre
    CRITICAL_HIT = 11  # Golpe crítico
    MISS = 12  # Fallo

    # Efectos de estado
    PARALYZED = 20  # Paralizado
    INVISIBLE = 21  # Invisible
    MEDITATION = 22  # Meditación

    # Efectos ambientales
    SMOKE = 30  # Humo
    EXPLOSION = 31  # Explosión
    SPARKLES = 32  # Destellos

    # TODO: Completar con más IDs según los efectos del cliente
    # Estos valores son aproximados y deben verificarse con el cliente real


class FXLoops(IntEnum):
    """Constantes para loops de efectos visuales."""

    ONCE = 1  # Reproducir una vez y desaparecer
    INFINITE = 0  # Reproducir infinitamente (o -1 según implementación)
    # Valores positivos = número específico de loops
