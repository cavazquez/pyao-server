# ruff: noqa: DOC201, DOC402
"""Representación eficiente de mapas usando bitmaps.

Reduce el uso de memoria de ~297 MB a <1 MB para datos de tiles.
Cada mapa de 100x100 tiles usa solo ~1.25 KB en vez de ~1 MB.
"""

from __future__ import annotations

import array
from collections.abc import Iterator
from dataclasses import dataclass, field

# Tamaño estándar de mapas en Argentum Online
MAP_WIDTH = 100
MAP_HEIGHT = 100
BITS_PER_BYTE = 8


@dataclass
class TileBitmap:
    """Bitmap eficiente para almacenar tiles de un tipo específico.

    Usa 1 bit por tile en vez de 16+ bytes por tupla (x, y).
    Un mapa 100x100 usa solo 1,250 bytes.
    """

    width: int = MAP_WIDTH
    height: int = MAP_HEIGHT
    _data: array.array[int] = field(default_factory=lambda: array.array("B"))

    def __post_init__(self) -> None:
        """Inicializa el array de bits."""
        if not self._data:
            # Calcular bytes necesarios: ceil(width * height / 8)
            num_bytes = (self.width * self.height + BITS_PER_BYTE - 1) // BITS_PER_BYTE
            self._data = array.array("B", [0] * num_bytes)

    def _get_index(self, x: int, y: int) -> tuple[int, int]:
        """Calcula índice de byte y bit para una coordenada."""
        if not (0 <= x < self.width and 0 <= y < self.height):
            return -1, -1
        bit_index = y * self.width + x
        byte_index = bit_index // BITS_PER_BYTE
        bit_offset = bit_index % BITS_PER_BYTE
        return byte_index, bit_offset

    def set_tile(self, x: int, y: int) -> None:
        """Marca un tile como activo."""
        byte_idx, bit_off = self._get_index(x, y)
        if byte_idx >= 0:
            self._data[byte_idx] |= 1 << bit_off

    def clear(self, x: int, y: int) -> None:
        """Desmarca un tile."""
        byte_idx, bit_off = self._get_index(x, y)
        if byte_idx >= 0:
            self._data[byte_idx] &= ~(1 << bit_off)

    def get(self, x: int, y: int) -> bool:
        """Verifica si un tile está activo."""
        byte_idx, bit_off = self._get_index(x, y)
        if byte_idx < 0:
            return False
        return bool(self._data[byte_idx] & (1 << bit_off))

    def __contains__(self, coord: tuple[int, int]) -> bool:
        """Permite usar 'in' operator: (x, y) in bitmap."""
        return self.get(coord[0], coord[1])

    def count(self) -> int:
        """Cuenta tiles activos."""
        total = 0
        for byte in self._data:
            total += byte.bit_count()
        return total

    def __len__(self) -> int:
        """Retorna cantidad de tiles activos."""
        return self.count()

    def __iter__(self) -> Iterator[tuple[int, int]]:
        """Itera sobre coordenadas de tiles activos."""
        for y in range(self.height):
            for x in range(self.width):
                if self.get(x, y):
                    yield (x, y)

    @classmethod
    def from_set(
        cls,
        coords: set[tuple[int, int]],
        width: int = MAP_WIDTH,
        height: int = MAP_HEIGHT,
    ) -> TileBitmap:
        """Crea bitmap desde un set de coordenadas."""
        bitmap = cls(width=width, height=height)
        for x, y in coords:
            bitmap.set_tile(x, y)
        return bitmap

    def to_set(self) -> set[tuple[int, int]]:
        """Convierte bitmap a set de coordenadas."""
        return set(self)

    def memory_bytes(self) -> int:
        """Retorna bytes usados por el bitmap."""
        return len(self._data)


@dataclass
class MapBitmaps:
    """Colección de bitmaps para un mapa completo."""

    blocked: TileBitmap = field(default_factory=TileBitmap)
    water: TileBitmap = field(default_factory=TileBitmap)
    trees: TileBitmap = field(default_factory=TileBitmap)
    mines: TileBitmap = field(default_factory=TileBitmap)
    anvils: TileBitmap = field(default_factory=TileBitmap)
    forges: TileBitmap = field(default_factory=TileBitmap)

    def is_blocked(self, x: int, y: int) -> bool:
        """Verifica si un tile está bloqueado."""
        return self.blocked.get(x, y)

    def is_water(self, x: int, y: int) -> bool:
        """Verifica si un tile es agua."""
        return self.water.get(x, y)

    def has_tree(self, x: int, y: int) -> bool:
        """Verifica si hay un árbol en el tile."""
        return self.trees.get(x, y)

    def has_mine(self, x: int, y: int) -> bool:
        """Verifica si hay un yacimiento en el tile."""
        return self.mines.get(x, y)

    def memory_bytes(self) -> int:
        """Retorna bytes totales usados."""
        return (
            self.blocked.memory_bytes()
            + self.water.memory_bytes()
            + self.trees.memory_bytes()
            + self.mines.memory_bytes()
            + self.anvils.memory_bytes()
            + self.forges.memory_bytes()
        )

    @classmethod
    def from_dict(cls, resources: dict[str, set[tuple[int, int]]]) -> MapBitmaps:
        """Crea MapBitmaps desde diccionario de recursos."""
        return cls(
            blocked=TileBitmap.from_set(resources.get("blocked", set())),
            water=TileBitmap.from_set(resources.get("water", set())),
            trees=TileBitmap.from_set(resources.get("trees", set())),
            mines=TileBitmap.from_set(resources.get("mines", set())),
            anvils=TileBitmap.from_set(resources.get("anvils", set())),
            forges=TileBitmap.from_set(resources.get("forges", set())),
        )


class SpatialIndex:
    """Índice espacial para búsquedas O(1) de tiles.

    Combina múltiples bitmaps en un solo índice para consultas rápidas.
    """

    def __init__(self) -> None:
        """Inicializa el índice espacial."""
        self._maps: dict[int, MapBitmaps] = {}

    def add_map(self, map_id: int, resources: dict[str, set[tuple[int, int]]]) -> None:
        """Agrega un mapa al índice."""
        self._maps[map_id] = MapBitmaps.from_dict(resources)

    def get_map(self, map_id: int) -> MapBitmaps | None:
        """Obtiene bitmaps de un mapa."""
        return self._maps.get(map_id)

    def is_blocked(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si un tile está bloqueado (O(1))."""
        bitmaps = self._maps.get(map_id)
        if bitmaps is None:
            return False
        return bitmaps.is_blocked(x, y)

    def is_water(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si un tile es agua (O(1))."""
        bitmaps = self._maps.get(map_id)
        if bitmaps is None:
            return False
        return bitmaps.is_water(x, y)

    def is_walkable(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si se puede caminar en un tile (O(1))."""
        bitmaps = self._maps.get(map_id)
        if bitmaps is None:
            return True  # Si no hay datos, asumimos caminable
        return not bitmaps.is_blocked(x, y)

    def has_resource(self, map_id: int, x: int, y: int) -> str | None:
        """Retorna tipo de recurso en un tile o None."""
        bitmaps = self._maps.get(map_id)
        if bitmaps is None:
            return None
        if bitmaps.has_tree(x, y):
            return "tree"
        if bitmaps.has_mine(x, y):
            return "mine"
        if bitmaps.anvils.get(x, y):
            return "anvil"
        if bitmaps.forges.get(x, y):
            return "forge"
        return None

    def memory_bytes(self) -> int:
        """Retorna memoria total usada."""
        return sum(m.memory_bytes() for m in self._maps.values())

    def __len__(self) -> int:
        """Retorna cantidad de mapas indexados."""
        return len(self._maps)
