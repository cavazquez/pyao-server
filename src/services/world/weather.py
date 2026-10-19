"""Clima explícito por mapa del catálogo propio, persistido e idempotente."""

import tomllib
from typing import TYPE_CHECKING, Any, cast

from src.runtime_paths import data_dir
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

OUTDOOR_TYPES = frozenset({"city", "wilderness", "water"})
MAX_INTENSITY = 100


class WeatherState:
    """Los interiores y mapas desconocidos permanecen sin lluvia."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Lee la clasificación propia, sin importar números de mapas ajenos."""
        self.deps = deps
        self.maps = tomllib.loads((data_dir() / "world/map_metadata.toml").read_text())

    async def snapshot(self, user: int) -> dict[str, Any]:
        """Obtiene el clima actual, sin toggles relativos a un estado del cliente.

        Returns:
            Mapa, exposición e intensidad autoritativa.
        """
        position = await self.deps.player_repo.get_position(user) or {}
        map_id = int(position.get("map", 0))
        outdoor = self.maps.get(f"map_{map_id}", {}).get("type") in OUTDOOR_TYPES
        fields = (
            await self.deps.redis_client.redis.hgetall(f"world:weather:{map_id}") if outdoor else {}
        )
        raining = outdoor and fields.get("raining") == "1"
        return {
            "map": map_id,
            "outdoor": outdoor,
            "raining": raining,
            "intensity": max(0, min(MAX_INTENSITY, int(fields.get("intensity", 0))))
            if raining
            else 0,
        }

    async def set(self, user: int, params: dict[str, Any], identity: str) -> dict[str, Any]:
        """Permite un estado explícito sólo a operadores autorizados.

        Returns:
            Resultado sin cambiar interiores ni mapas ajenos al catálogo.
        """
        if not await self.deps.account_repo.is_gm_by_user_id(user):
            return {"applied": False, "message": "No tienes permisos de Game Master."}
        map_id = params["map"]
        if (
            self.maps.get(f"map_{map_id}", {}).get("type") not in OUTDOOR_TYPES
            or not 0 <= params["intensity"] <= MAX_INTENSITY
        ):
            return {"applied": False, "message": "Mapa exterior o intensidad inválidos."}
        key = f"world:weather:{map_id}"

        def decide(snapshot: Snapshot) -> Decision:
            before = cast("dict[str, str]", snapshot[key])
            fields = {
                "raining": "1" if params["raining"] else "0",
                "intensity": str(params["intensity"] if params["raining"] else 0),
            }
            changed = any(before.get(field) != value for field, value in fields.items())
            return Decision(
                {"applied": True, "message": "Clima actualizado."},
                {
                    key: {
                        **fields,
                        "version": "1",
                        "revision": str(int(before.get("revision", 0)) + int(changed)),
                    }
                },
            )

        return await transact(
            self.deps.redis_client.redis,
            (Resource(key, "hash"),),
            identity,
            {"weather": map_id, "actor": user, **params},
            decide,
        )
