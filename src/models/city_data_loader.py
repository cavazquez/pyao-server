"""Carga las seis ciudades del contrato propio en Redis antes de aceptar clientes."""

import asyncio
import tomllib

from src.game.character_constants import HOME_ID_TO_NAME
from src.runtime_paths import data_dir
from src.utils.base_data_loader import BaseDataLoader
from src.utils.redis_config import RedisKeys


class CityDataLoader(BaseDataLoader):
    """Publica spawns inmutables sin modificar posiciones de personajes existentes."""

    def get_name(self) -> str:
        """Devuelve el nombre del catálogo.

        Returns:
            Identificador del loader de ciudades.
        """
        return "Home Cities"

    @staticmethod
    def _read() -> dict[int, dict[str, str]]:
        """Valida y prepara el catálogo fuera del event loop.

        Returns:
            Los seis spawns indexados por el ID de home del protocolo.
        """
        with (data_dir() / "world/cities.toml").open("rb") as source:
            rows = tomllib.load(source)["cities"]["city"]
        cities = {entry["name"]: entry for entry in rows}
        return {
            home: {
                "map": str(int(cities[name]["map_id"])),
                "x": str(int(cities[name]["spawn_x"])),
                "y": str(int(cities[name]["spawn_y"])),
                "heading": "3",
            }
            for home, name in HOME_ID_TO_NAME.items()
        }

    async def load(self) -> None:
        """Carga sólo el catálogo de spawns, nunca estado editable de jugadores."""
        for home, spawn in (await asyncio.to_thread(self._read)).items():
            await self.redis_client.hset(RedisKeys.home_spawn(home), mapping=spawn)
