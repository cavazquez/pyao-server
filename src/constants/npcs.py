"""Enums de NPCs y criaturas."""

from enum import IntEnum


class NPCBodyID(IntEnum):
    """Body IDs de NPCs y criaturas.

    Verificados desde ArgentumOnline 0.13.3 - server/Dat/NPCs.dat
    """

    # Criaturas hostiles (ordenadas por nivel)
    MURCIELAGO = 9
    LOBO = 10
    ESQUELETO = 12
    SERPIENTE = 13
    GOBLIN = 14
    DRAGON_ROJO = 41
    ARANA_GIGANTE = 42
    OGRO = 76
    GRAN_DRAGON_ROJO = 82
    DEMONIO = 83
    ORCO = 185
    ZOMBIE = 196

    # NPCs amigables/servicios
    COMERCIANTE = 501
    GUARDIA = 502
    BANQUERO = 504
    ENTRENADOR = 505
