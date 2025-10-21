"""Constantes de gráficos (GrhIndex)."""

# Rangos de GrhIndex para recursos naturales
# Basado en el análisis del WorldEditor de AO VB6

WATER_GRAPHIC_RANGES = [
    (1505, 1520),  # Agua tipo 1
    (5665, 5680),  # Agua tipo 2
    (13547, 13562),  # Agua tipo 3
]

# TODO: Agregar rangos para árboles y yacimientos cuando se identifiquen
TREE_GRAPHIC_RANGES: list[tuple[int, int]] = []
MINE_GRAPHIC_RANGES: list[tuple[int, int]] = []
