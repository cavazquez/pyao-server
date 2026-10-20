"""Tabla por mapa con una vista mutable compatible de claves (mapa, x, y)."""

from collections.abc import Iterator, Mapping, MutableMapping


class MapTileIndex[T](MutableMapping[tuple[int, int, int], T]):
    """Almacena cada valor una sola vez y acota los recorridos al mapa consultado."""

    def __init__(self) -> None:
        """Crea buckets vacíos; el contador se mantiene al modificar la tabla."""
        self._maps: dict[int, dict[tuple[int, int], T]] = {}
        self._size = 0

    def __getitem__(self, key: tuple[int, int, int]) -> T:
        """Consulta una casilla por la clave plana de compatibilidad.

        Returns:
            Valor almacenado en esa casilla.
        """
        map_id, x, y = key
        return self._maps[map_id][x, y]

    def __setitem__(self, key: tuple[int, int, int], value: T) -> None:
        """Asigna una casilla y mantiene el contador global."""
        map_id, x, y = key
        tiles = self._maps.setdefault(map_id, {})
        if (x, y) not in tiles:
            self._size += 1
        tiles[x, y] = value

    def __delitem__(self, key: tuple[int, int, int]) -> None:
        """Retira una casilla y descarta buckets vacíos."""
        map_id, x, y = key
        tiles = self._maps[map_id]
        del tiles[x, y]
        self._size -= 1
        if not tiles:
            del self._maps[map_id]

    def __iter__(self) -> Iterator[tuple[int, int, int]]:
        """Itera la vista plana sólo cuando se solicita el mundo completo.

        Yields:
            Claves (mapa, x, y) de las casillas ocupadas.
        """
        for map_id, tiles in self._maps.items():
            for x, y in tiles:
                yield map_id, x, y

    def __len__(self) -> int:
        """Consulta el contador de casillas en tiempo constante.

        Returns:
            Cantidad de casillas de todos los mapas.
        """
        return self._size

    def in_map(self, map_id: int) -> Mapping[tuple[int, int], T]:
        """Consulta un mapa sin materializar ni escanear otros mapas.

        Returns:
            Vista de sólo lectura del bucket solicitado.
        """
        return self._maps.get(map_id, {})

    def pop_map(self, map_id: int) -> dict[tuple[int, int], T]:
        """Retira un bucket sin consultar el resto de la tabla.

        Returns:
            Las casillas retiradas de ese mapa.
        """
        tiles = self._maps.pop(map_id, {})
        self._size -= len(tiles)
        return tiles

    def replace_map(self, map_id: int, tiles: dict[tuple[int, int], T]) -> None:
        """Reemplaza el snapshot de un mapa sin mantener un índice duplicado."""
        self.pop_map(map_id)
        if tiles:
            self._maps[map_id] = tiles
            self._size += len(tiles)
