"""Constantes del juego organizadas en enums y valores."""

from src.constants.effects import FXType
from src.constants.graphics import WATER_GRAPHIC_RANGES
from src.constants.items import ResourceItemID, ToolID
from src.constants.map import MAP_SIZE
from src.constants.npcs import NPCBodyID

__all__ = [
    "MAP_SIZE",
    "WATER_GRAPHIC_RANGES",
    "FXType",
    "NPCBodyID",
    "ResourceItemID",
    "ToolID",
]
