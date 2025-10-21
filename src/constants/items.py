"""Enums de items del juego."""

from enum import IntEnum


class ToolID(IntEnum):
    """IDs de herramientas de trabajo."""

    HACHA_LENADOR = 561
    PIQUETE_MINERO = 562
    CANA_PESCAR = 563


class ResourceItemID(IntEnum):
    """IDs de items obtenidos de recursos naturales."""

    LENA = 58
    MINERAL_HIERRO = 192
    PESCADO = 139
