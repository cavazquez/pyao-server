"""Enums de efectos visuales (FX)."""

from enum import IntEnum


class FXType(IntEnum):
    """Tipos de efectos visuales del juego.

    Basado en el sistema de FX de Argentum Online VB6.
    """

    # Efectos de muerte/daño
    BLOOD = 5
    POISON = 10

    # Efectos de curación/buff
    HEAL = 15
    MEDITATION = 18

    # Efectos de fuego
    FIRE_AURA = 20
    FIRE_EXPLOSION = 25

    # Efectos oscuros
    DARK_AURA = 50

    # Efectos de spawn
    SPAWN = 1
