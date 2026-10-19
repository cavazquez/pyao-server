"""Distancia al litoral sobre el agua real, con continuidad entre salidas marinas."""

import json
import operator
import random
import tomllib
from collections import deque
from pathlib import Path
from typing import TYPE_CHECKING

from src.runtime_paths import data_dir

if TYPE_CHECKING:
    from src.services.map.map_resources_service import MapResourcesService

Tile = tuple[int, int, int]
MAX_COORD = 100
EDGE_LOW = 9
EDGE_HIGH = 92
SIDES = ((1, 0), (-1, 0), (0, 1), (0, -1))


class FishingZones:
    """Cachea cada masa de agua; el cliente nunca elige banda, especie ni tirada."""

    def __init__(self, terrain: MapResourcesService, rules: Path | None = None) -> None:
        """Carga reglas del dataset y posterga la clasificación hasta su primer uso.

        Raises:
            ValueError: Si falta una banda costera o la distribución es inválida.
        """
        self.terrain = terrain
        path = rules or data_dir() / "fishing.toml"
        with path.open("rb") as source:
            self.rules = tomllib.load(source)
        self.bands = sorted(self.rules["band"], key=operator.itemgetter("min_distance"))
        if not self.bands or self.bands[0]["min_distance"] != 0:
            msg = "La pesca necesita una banda costera desde distancia cero"
            raise ValueError(msg)
        for band in self.bands:
            if len(band["items"]) != len(band["weights"]) or any(w <= 0 for w in band["weights"]):
                msg = "Distribución de pesca inválida"
                raise ValueError(msg)
        with (data_dir() / "world/map_metadata.toml").open("rb") as source:
            metadata = tomllib.load(source)
        self.sea_maps = set(self.rules.get("marine_maps", [])) or {
            int(key.removeprefix("map_"))
            for key, row in metadata.items()
            if row.get("type") == "water"
        }
        self.links: dict[Tile, list[Tile]] = {}
        for chunk in sorted(
            getattr(terrain, "maps_dir", Path("__no_map_data__")).glob("transitions_*.json")
        ):
            for line in chunk.read_text().splitlines():
                if not line.strip():
                    continue
                row = json.loads(line)
                for exit_tile in row.get("exits", []):
                    x, y = int(exit_tile["x"]), int(exit_tile["y"])
                    tx, ty = int(exit_tile["to_x"]), int(exit_tile["to_y"])
                    # Sólo bordes opuestos; un teleport interior no une dos mares.
                    adjacent = (
                        (x <= EDGE_LOW and tx >= EDGE_HIGH)
                        or (x >= EDGE_HIGH and tx <= EDGE_LOW)
                        or (y <= EDGE_LOW and ty >= EDGE_HIGH)
                        or (y >= EDGE_HIGH and ty <= EDGE_LOW)
                    )
                    a = int(row["from_map"]), x, y
                    b = int(exit_tile["to_map"]), tx, ty
                    if adjacent and self._water(a) and self._water(b):
                        self.links.setdefault(a, []).append(b)
                        self.links.setdefault(b, []).append(a)
        self.distance: dict[Tile, int] = {}
        self.marine: set[Tile] = set()

    def _water(self, tile: Tile) -> bool:
        return self.terrain.has_water(*tile)

    def classify(self, tile: Tile) -> tuple[str, int]:
        """Devuelve banda y distancia; agua interior conserva siempre pesca simple.

        Returns:
            Nombre de banda y distancia mínima al litoral real.
        """
        if tile not in self.distance:
            self._classify_component(tile)
        distance = self.distance.get(tile, 0)
        if tile not in self.marine:
            return str(self.bands[0]["name"]), distance
        band = self.bands[0]
        for candidate in self.bands:
            if distance >= candidate["min_distance"]:
                band = candidate
        return str(band["name"]), distance

    def _classify_component(self, start: Tile) -> None:
        if not self._water(start):
            self.distance[start] = 0
            return
        found, queue, shores = {start}, deque([start]), []
        while queue:
            tile = queue.popleft()
            m, x, y = tile
            neighbours = [
                (m, x + dx, y + dy)
                for dx, dy in SIDES
                if 1 <= x + dx <= MAX_COORD and 1 <= y + dy <= MAX_COORD
            ]
            if any(not self._water(t) for t in neighbours):
                shores.append(tile)
            for other in [*neighbours, *self.links.get(tile, [])]:
                if other not in found and self._water(other):
                    found.add(other)
                    queue.append(other)
        # Distancia mínima a cualquier isla/costa, también a través de mapas vecinos.
        distance = dict.fromkeys(shores, 0)
        queue = deque(shores)
        while queue:
            tile = queue.popleft()
            m, x, y = tile
            for other in [*((m, x + dx, y + dy) for dx, dy in SIDES), *self.links.get(tile, [])]:
                if other in found and other not in distance:
                    distance[other] = distance[tile] + 1
                    queue.append(other)
        self.distance.update({t: distance.get(t, 0) for t in found})
        # Sin litoral verificable no se inventa alta mar ni premio mayor.
        if shores and any(t[0] in self.sea_maps for t in found):
            self.marine.update(found)

    def catch(self, tile: Tile) -> tuple[int, str, int]:
        """Elige una especie una sola vez antes del WATCH/reintento de inventario.

        Returns:
            ID de especie, nombre de banda y distancia a la costa.
        """
        name, distance = self.classify(tile)
        band = next(row for row in self.bands if row["name"] == name)
        item = random.choices(band["items"], band["weights"], k=1)[0]
        return int(item), name, distance
