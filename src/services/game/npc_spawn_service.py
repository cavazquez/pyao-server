"""Servicio de spawning de NPCs en el mundo.

Gestiona la aparición, posicionamiento y ciclo de vida
de los NPCs dentro de los mapas del juego.
"""

import logging
import random
from pathlib import Path
from tomllib import load as tomllib_load
from typing import Any, ClassVar

from .npc_service import get_npc_service

logger = logging.getLogger(__name__)

# Rango de visión para NPCs (en tiles)
NPC_VISION_RANGE = 15
SPAWN_DISTANCE = 20  # Distancia mínima del jugador para spawn

# Constantes de mapa
MAP_MIN_X = 1
MAP_MAX_X = 100
MAP_MIN_Y = 1
MAP_MAX_Y = 100
NPC_MOVE_CHANCE = 0.1  # 10% probabilidad de moverse


class NPCSpawnService:
    """Servicio para manejar el spawning de NPCs en el mundo."""

    _instance: ClassVar[NPCSpawnService | None] = None
    _initialized: bool = False

    def __new__(cls, *args: Any, **kwargs: Any) -> NPCSpawnService:  # noqa: ANN401, ARG004, PYI034
        """Garantiza que todas las instancias compartan el mismo objeto singleton."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def get_instance(cls, data_dir: Path | str = "data") -> NPCSpawnService:
        """Obtiene la instancia singleton del servicio de spawn.

        Returns:
            Instancia única de ``NPCSpawnService``.
        """
        if cls._instance is None:
            cls(data_dir=data_dir)
        return cls._instance  # type: ignore[return-value]

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia la instancia singleton."""
        cls._instance = None
        cls._initialized = False

    def __init__(self, data_dir: Path | str = "data") -> None:
        """Inicializa el servicio de spawning.

        Args:
            data_dir: Directorio donde se encuentran los datos.
        """
        if getattr(self, "_initialized", False):
            return

        self.data_dir = Path(data_dir)
        self.map_npcs: dict[int, dict[str, Any]] = {}
        self.spawned_npcs: dict[str, dict[str, Any]] = {}  # npc_id -> npc_data
        self.npc_positions: dict[str, dict[str, int]] = {}  # npc_id -> {map, x, y}

        # Cargar configuración de NPCs por mapa
        self._load_map_npcs()

        self._initialized = True
        NPCSpawnService._initialized = True
        NPCSpawnService._instance = self

    def _load_map_npcs(self) -> None:
        """Carga las configuraciones de NPCs por mapa."""
        try:
            map_npcs_file = self.data_dir / "map_npcs.toml"
            if map_npcs_file.exists():
                with map_npcs_file.open("rb") as f:
                    data = tomllib_load(f)
                    raw_map_npcs = data.get("map_npcs", {})
                    # Convertir keys de string a int
                    self.map_npcs = {int(k): v for k, v in raw_map_npcs.items()}
                logger.info("Cargados NPCs para %d mapas", len(self.map_npcs))
            else:
                logger.warning("No existe map_npcs.toml, usando defaults")
                self._create_default_map_npcs()
        except Exception:
            logger.exception("Error cargando configuración de NPCs por mapa")

    def _create_default_map_npcs(self) -> None:
        """Crea configuración por defecto de NPCs en mapas."""
        self.map_npcs = {
            1: {  # Ullathorpe
                "spawn_points": [
                    {"npc_id": 1, "x": 50, "y": 50, "direction": 3},
                    {"npc_id": 3, "x": 60, "y": 45, "direction": 1},
                ],
                "random_spawns": [
                    {
                        "npc_type": "hostile",
                        "count": 3,
                        "area": {"x1": 70, "y1": 70, "x2": 90, "y2": 90},
                    }
                ],
            },
            34: {  # Nix
                "spawn_points": [
                    {"npc_id": 1, "x": 30, "y": 30, "direction": 2},
                    {"npc_id": 2, "x": 40, "y": 35, "direction": 4},
                ]
            },
        }

    def spawn_npcs_for_player(
        self, player_map: int, player_x: int, player_y: int
    ) -> list[dict[str, Any]]:
        """Spawnea NPCs para un jugador en su área de visión.

        Args:
            player_map: Mapa donde está el jugador.
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.

        Returns:
            Lista de NPCs en rango de visión del jugador.
        """
        visible_npcs = []
        map_config = self.map_npcs.get(player_map, {})

        # Spawnea NPCs fijos en puntos específicos
        for spawn_point in map_config.get("spawn_points", []):
            npc_id = spawn_point["npc_id"]
            npc_x = spawn_point["x"]
            npc_y = spawn_point["y"]

            # Verificar si está en rango de visión
            if NPCSpawnService._is_in_vision_range(player_x, player_y, npc_x, npc_y):
                npc_key = f"{player_map}_{npc_id}_{npc_x}_{npc_y}"

                if npc_key not in self.spawned_npcs:
                    # Obtener datos del NPC desde NPCService
                    npc_service = get_npc_service()
                    npc_data = npc_service.get_npc_by_id(npc_id)

                    if npc_data:
                        npc_instance = {
                            "id": npc_data["id"],
                            "name": npc_data.get("nombre", npc_data.get("name", "Sin nombre")),
                            "map": player_map,
                            "x": npc_x,
                            "y": npc_y,
                            "direction": spawn_point.get("direction", 3),
                            "type": npc_data.get("npc_type", 0),
                            "category": npc_data.get("category", "NPCS VARIOS"),
                            "tags": npc_data.get("tags", []),
                            "appearance": npc_data.get("appearance", {}),
                            "hostile": npc_service.is_npc_hostile(npc_id),
                            "trader": npc_service.can_npc_trade(npc_id),
                            "instance_id": npc_key,
                        }

                        self.spawned_npcs[npc_key] = npc_instance
                        self.npc_positions[npc_key] = {"map": player_map, "x": npc_x, "y": npc_y}

                # Agregar a visibles solo si existe en spawned_npcs
                if npc_key in self.spawned_npcs:
                    visible_npcs.append(self.spawned_npcs[npc_key])

        # Spawnea NPCs aleatorios en áreas designadas
        for random_spawn in map_config.get("random_spawns", []):
            spawned_count = len(
                [
                    npc
                    for npc in self.spawned_npcs.values()
                    if npc["map"] == player_map and npc.get("random_spawn")
                ]
            )

            if spawned_count < random_spawn["count"]:
                self._spawn_random_npc(random_spawn, player_map, player_x, player_y, visible_npcs)

        return visible_npcs

    def _spawn_random_npc(
        self,
        spawn_config: dict[str, Any],
        map_num: int,
        player_x: int,
        player_y: int,
        visible_npcs: list[dict[str, Any]],
    ) -> None:
        """Spawnea un NPC aleatorio en un área designada."""
        npc_service = get_npc_service()

        if spawn_config["npc_type"] == "hostile":
            # Obtener NPC hostil aleatorio
            hostiles = npc_service.get_hostile_npcs()
            if not hostiles:
                return

            npc_template = random.choice(hostiles)
        else:
            # Por defecto, NPC común
            all_npcs = npc_service.get_all_npcs()
            if not all_npcs:
                return
            npc_template = random.choice(all_npcs)

        # Generar posición aleatoria en el área
        area = spawn_config["area"]
        npc_x = random.randint(area["x1"], area["x2"])
        npc_y = random.randint(area["y1"], area["y2"])

        # Verificar si está en rango de visión
        if NPCSpawnService._is_in_vision_range(player_x, player_y, npc_x, npc_y):
            npc_key = f"{map_num}_random_{len(self.spawned_npcs)}"

            npc_instance = {
                "id": npc_template["id"],
                "name": npc_template["name"],
                "map": map_num,
                "x": npc_x,
                "y": npc_y,
                "direction": random.randint(1, 4),
                "type": npc_template["npc_type"],
                "category": npc_template["category"],
                "tags": npc_template["tags"],
                "appearance": npc_template.get("appearance", {}),
                "hostile": npc_service.is_npc_hostile(npc_template["id"]),
                "trader": npc_service.can_npc_trade(npc_template["id"]),
                "instance_id": npc_key,
                "random_spawn": True,
            }

            self.spawned_npcs[npc_key] = npc_instance
            self.npc_positions[npc_key] = {"map": map_num, "x": npc_x, "y": npc_y}
            visible_npcs.append(npc_instance)

    @staticmethod
    def _is_in_vision_range(player_x: int, player_y: int, npc_x: int, npc_y: int) -> bool:
        """Verifica si un NPC está en el rango de visión del jugador.

        Args:
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.
            npc_x: Posición X del NPC.
            npc_y: Posición Y del NPC.

        Returns:
            True si el NPC está en rango de visión, False en caso contrario.
        """
        distance = abs(player_x - npc_x) + abs(player_y - npc_y)
        return distance <= NPC_VISION_RANGE

    def get_npc_at_position(self, map_num: int, x: int, y: int) -> dict[str, Any] | None:
        """Obtiene el NPC en una posición específica.

        Args:
            map_num: Número del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Datos del NPC o None si no hay nadie.
        """
        for npc in self.spawned_npcs.values():
            if npc["map"] == map_num and npc["x"] == x and npc["y"] == y:
                return npc
        return None

    def update_npc_position(self, instance_id: str, new_x: int, new_y: int, direction: int) -> bool:
        """Actualiza la posición de un NPC.

        Args:
            instance_id: ID único de la instancia del NPC.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            direction: Nueva dirección (1-4).

        Returns:
            True si se actualizó correctamente.
        """
        if instance_id in self.spawned_npcs:
            npc = self.spawned_npcs[instance_id]
            npc["x"] = new_x
            npc["y"] = new_y
            npc["direction"] = direction

            if instance_id in self.npc_positions:
                self.npc_positions[instance_id]["x"] = new_x
                self.npc_positions[instance_id]["y"] = new_y

            return True
        return False

    def despawn_npc(self, instance_id: str) -> bool:
        """Elimina un NPC del mundo.

        Args:
            instance_id: ID único de la instancia del NPC.

        Returns:
            True si se eliminó correctamente.
        """
        if instance_id in self.spawned_npcs:
            del self.spawned_npcs[instance_id]

        if instance_id in self.npc_positions:
            del self.npc_positions[instance_id]

        return True

    def despawn_npcs_out_of_range(self, player_map: int, player_x: int, player_y: int) -> list[str]:
        """Elimina NPCs que están fuera del rango de visión del jugador.

        Args:
            player_map: Mapa del jugador.
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.

        Returns:
            Lista de IDs de NPCs eliminados.
        """
        despawned = []

        for instance_id, npc in list(self.spawned_npcs.items()):
            if npc["map"] != player_map:
                continue

            if not self._is_in_vision_range(player_x, player_y, npc["x"], npc["y"]):
                despawned.append(instance_id)
                self.despawn_npc(instance_id)

        return despawned

    def get_all_spawned_npcs(self) -> dict[str, dict[str, Any]]:
        """Retorna todos los NPCs spawneados.

        Returns:
            Copia del diccionario con todos los NPCs spawneados.
        """
        return self.spawned_npcs.copy()

    def get_npcs_in_map(self, map_num: int) -> list[dict[str, Any]]:
        """Retorna todos los NPCs en un mapa específico.

        Args:
            map_num: Número del mapa.

        Returns:
            Lista de NPCs en el mapa.
        """
        return [npc for npc in self.spawned_npcs.values() if npc["map"] == map_num]

    def get_spawn_statistics(self) -> dict[str, Any]:
        """Retorna estadísticas de spawning.

        Returns:
            Diccionario con estadísticas de spawn.
        """
        total_spawned = len(self.spawned_npcs)
        npc_by_map: dict[int, int] = {}
        hostile_count = 0
        trader_count = 0

        for npc in self.spawned_npcs.values():
            map_num = npc["map"]
            npc_by_map[map_num] = npc_by_map.get(map_num, 0) + 1

            if npc["hostile"]:
                hostile_count += 1

            if npc["trader"]:
                trader_count += 1

        return {
            "total_spawned": total_spawned,
            "npcs_by_map": npc_by_map,
            "hostile_count": hostile_count,
            "trader_count": trader_count,
            "configured_maps": len(self.map_npcs),
        }


def get_npc_spawn_service() -> NPCSpawnService:
    """Obtiene la instancia singleton del ``NPCSpawnService``.

    Returns:
        Instancia única del servicio de spawn de NPCs.
    """
    return NPCSpawnService.get_instance()


def initialize_npc_spawn_service(data_dir: Path | str) -> NPCSpawnService:
    """Inicializa el servicio singleton con directorio personalizado.

    Args:
        data_dir: Directorio donde se encuentran los datos.

    Returns:
        Instancia del NPCSpawnService.
    """
    NPCSpawnService.reset_instance()
    return NPCSpawnService.get_instance(data_dir=data_dir)
