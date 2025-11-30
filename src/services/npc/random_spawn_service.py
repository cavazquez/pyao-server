"""Servicio para manejar spawns aleatorios dinámicos de NPCs.

Este servicio gestiona NPCs que spawnean dinámicamente cuando un jugador
entra en áreas designadas. Los NPCs persisten hasta que mueren (no se
despawnean cuando los jugadores se alejan).

En multijugador, el sistema spawnea hasta un límite máximo por área
configurado, independientemente de cuántos jugadores estén presentes.
Los NPCs solo desaparecen cuando mueren en combate.
"""

import logging
import random
import time
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.models.npc import NPC
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)

# Constantes
RANDOM_SPAWN_RESPAWN_COOLDOWN = 60.0  # Cooldown de respawn en segundos
MAX_SPAWN_ATTEMPTS = 10  # Intentos máximos para encontrar tile libre


class RandomSpawnService:
    """Servicio para gestionar spawns aleatorios dinámicos de NPCs."""

    def __init__(self, npc_service: NPCService, map_manager: MapManager) -> None:
        """Inicializa el servicio de random spawns.

        Args:
            npc_service: Servicio de NPCs para crear instancias.
            map_manager: Gestor de mapas para verificar tiles libres.
        """
        self.npc_service = npc_service
        self.map_manager = map_manager

        # Configuración de random spawns por mapa
        self._random_spawn_configs: dict[int, list[dict[str, Any]]] = {}

        # Tracking de NPCs random spawneados: {instance_id: spawn_info}
        self._random_spawned_npcs: dict[str, dict[str, Any]] = {}

        # Tracking de cooldowns de respawn por área: {(map_id, area_key): last_spawn_time}
        self._respawn_cooldowns: dict[tuple[int, str], float] = {}

    def load_random_spawn_configs(self, spawns_path: Path | str) -> None:
        """Carga la configuración de random spawns desde map_npcs.toml.

        Args:
            spawns_path: Ruta al archivo map_npcs.toml.
        """
        path = Path(spawns_path)
        if not path.exists():
            logger.warning("Archivo de spawns no encontrado: %s", spawns_path)
            return

        try:
            with path.open("rb") as file:
                data = tomllib.load(file)
        except Exception:
            logger.exception("Error al leer archivo de spawns %s", spawns_path)
            return

        map_npcs = data.get("map_npcs")
        if not isinstance(map_npcs, dict):
            logger.warning("No se encontró la sección [map_npcs] en %s", spawns_path)
            return

        # Cargar random_spawns de cada mapa
        for map_id_str, map_data in map_npcs.items():
            if not isinstance(map_data, dict):
                continue

            try:
                map_id = int(map_id_str)
            except (ValueError, TypeError):
                continue

            random_spawns = map_data.get("random_spawns", [])
            if random_spawns:
                self._random_spawn_configs[map_id] = random_spawns
                logger.debug("Cargados %d random spawns para mapa %d", len(random_spawns), map_id)

        logger.info(
            "Configuración de random spawns cargada para %d mapas",
            len(self._random_spawn_configs),
        )

    async def spawn_random_npcs_for_player(
        self, map_id: int, player_x: int, player_y: int, vision_range: int = 15
    ) -> list[NPC]:
        """Spawnea NPCs aleatorios cuando un jugador entra en áreas designadas.

        IMPORTANTE: En multijugador, spawnea hasta el límite configurado por área,
        NO por jugador. Los NPCs persisten hasta que mueren o no hay jugadores cerca.

        Args:
            map_id: ID del mapa donde está el jugador.
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.
            vision_range: Rango de visión del jugador (default: 15 tiles).

        Returns:
            Lista de NPCs spawneados (solo los nuevos, no los que ya existían).
        """
        spawned: list[NPC] = []

        # Obtener configuraciones de random spawns para este mapa
        random_spawn_configs = self._random_spawn_configs.get(map_id, [])

        for spawn_config in random_spawn_configs:
            area = spawn_config.get("area", {})
            if not area:
                continue

            # Verificar si el jugador está cerca del área
            if not RandomSpawnService._is_player_near_area(player_x, player_y, area, vision_range):
                continue

            # Obtener NPCs ya spawneados en esta área (todos los NPCs, no solo de este jugador)
            area_key = RandomSpawnService._get_area_key(area)
            active_npcs = self._get_active_npcs_in_area(map_id, area_key)
            target_count = spawn_config.get("count", 0)

            # Verificar cooldown de respawn para esta área
            cooldown_key = (map_id, area_key)
            last_spawn_time = self._respawn_cooldowns.get(cooldown_key, 0.0)
            current_time = time.time()

            # Si aún no hay suficientes NPCs (límite global por área) y no hay cooldown, spawneamos
            if (
                len(active_npcs) < target_count
                and current_time - last_spawn_time >= RANDOM_SPAWN_RESPAWN_COOLDOWN
            ):
                # Intentar spawnear NPCs faltantes (hasta el límite)
                to_spawn = target_count - len(active_npcs)
                for _ in range(to_spawn):
                    npc = await self._try_spawn_random_npc(spawn_config, map_id, area, area_key)
                    if npc:
                        spawned.append(npc)
                        self._respawn_cooldowns[cooldown_key] = current_time

        return spawned

    async def on_random_npc_death(self, instance_id: str) -> None:
        """Notifica que un NPC random ha muerto y debe ser removido del tracking.

        Este método debe ser llamado cuando un NPC random muere para limpiar
        el tracking interno. Los NPCs solo desaparecen cuando mueren, no cuando
        los jugadores se alejan.

        Args:
            instance_id: ID de instancia del NPC que murió.
        """
        if instance_id in self._random_spawned_npcs:
            del self._random_spawned_npcs[instance_id]
            logger.debug("NPC random removido del tracking tras muerte: %s", instance_id)

    async def _try_spawn_random_npc(
        self,
        spawn_config: dict[str, Any],
        map_id: int,
        area: dict[str, int],
        area_key: str,
    ) -> NPC | None:
        """Intenta spawneear un NPC aleatorio en un área, verificando tiles libres.

        Args:
            spawn_config: Configuración del spawn (npc_type, etc.).
            map_id: ID del mapa.
            area: Área de spawn (x1, y1, x2, y2).
            area_key: Clave única del área para tracking.

        Returns:
            NPC spawneado o None si no se pudo.
        """
        # Seleccionar NPC aleatorio según tipo
        npc_id = await self._select_random_npc_id(spawn_config)
        if not npc_id:
            return None

        # Intentar encontrar una posición libre en el área
        for attempt in range(MAX_SPAWN_ATTEMPTS):
            npc_x = random.randint(area["x1"], area["x2"])
            npc_y = random.randint(area["y1"], area["y2"])
            heading = random.randint(1, 4)

            # Verificar si el tile está libre
            if self.map_manager.can_move_to(map_id, npc_x, npc_y):
                # Spawnear el NPC usando NPCService
                try:
                    npc = await self.npc_service.spawn_npc(npc_id, map_id, npc_x, npc_y, heading)
                    if npc:
                        # Trackear este NPC como random spawn
                        self._random_spawned_npcs[npc.instance_id] = {
                            "map_id": map_id,
                            "area_key": area_key,
                            "spawn_time": time.time(),
                        }
                        logger.debug(
                            "NPC random spawneado: %s (ID: %d) en mapa %d (%d,%d) área %s",
                            npc.name,
                            npc_id,
                            map_id,
                            npc_x,
                            npc_y,
                            area_key,
                        )
                        return npc
                except ValueError as e:
                    # Tile ocupado o error en spawn
                    logger.debug(
                        "No se pudo spawneear NPC en (%d,%d) mapa %d (intento %d/%d): %s",
                        npc_x,
                        npc_y,
                        map_id,
                        attempt + 1,
                        MAX_SPAWN_ATTEMPTS,
                        e,
                    )
                    continue

        logger.warning(
            "No se pudo encontrar tile libre para random spawn en mapa %d área %s "
            "después de %d intentos",
            map_id,
            area_key,
            MAX_SPAWN_ATTEMPTS,
        )
        return None

    async def _select_random_npc_id(self, spawn_config: dict[str, Any]) -> int | None:
        """Selecciona un ID de NPC aleatorio según la configuración.

        Args:
            spawn_config: Configuración del spawn con npc_type.

        Returns:
            ID del NPC seleccionado o None si no hay disponibles.
        """
        npc_type = spawn_config.get("npc_type", "common")

        # Obtener todos los IDs disponibles del catálogo
        all_npc_ids = self.npc_service.npc_catalog.get_all_npc_ids()
        if not all_npc_ids:
            return None

        if npc_type == "hostile":
            # Filtrar NPCs hostiles
            hostile_ids = []
            for npc_id in all_npc_ids:
                npc_data = self.npc_service.npc_catalog.get_npc_data(npc_id)
                if npc_data:
                    # Verificar si es hostil
                    # Puede venir como es_hostil (bool) o en behavior.hostile (int)
                    is_hostile = npc_data.get("es_hostil", False)
                    if not is_hostile:
                        behavior = npc_data.get("behavior")
                        if isinstance(behavior, dict):
                            is_hostile = bool(behavior.get("hostile", 0))

                    if is_hostile:
                        hostile_ids.append(npc_id)

            if hostile_ids:
                return random.choice(hostile_ids)
            # Si no hay hostiles, usar cualquier NPC como fallback
            return random.choice(all_npc_ids)

        # NPC común o cualquier otro tipo - seleccionar aleatoriamente
        return random.choice(all_npc_ids)

    @staticmethod
    def _get_area_key(area: dict[str, int]) -> str:
        """Genera una clave única para un área de spawn.

        Args:
            area: Diccionario con x1, y1, x2, y2.

        Returns:
            Clave única del área.
        """
        return f"{area['x1']}_{area['y1']}_{area['x2']}_{area['y2']}"

    @staticmethod
    def _is_player_near_area(
        player_x: int, player_y: int, area: dict[str, int], vision_range: int
    ) -> bool:
        """Verifica si el jugador está cerca de un área de spawn.

        Args:
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.
            area: Área de spawn (x1, y1, x2, y2).
            vision_range: Rango de visión del jugador.

        Returns:
            True si el jugador está cerca del área.
        """
        # Calcular punto central del área
        center_x = (area["x1"] + area["x2"]) // 2
        center_y = (area["y1"] + area["y2"]) // 2

        # Calcular distancia Manhattan
        distance = abs(player_x - center_x) + abs(player_y - center_y)

        # Verificar si está dentro del rango (considerando el tamaño del área)
        max_area_size = max(
            area["x2"] - area["x1"], area["y2"] - area["y1"]
        )  # Tamaño máximo del área
        effective_range = vision_range + max_area_size // 2

        return distance <= effective_range

    def _get_active_npcs_in_area(self, map_id: int, area_key: str) -> list[str]:
        """Obtiene los instance_ids de NPCs activos en un área.

        Args:
            map_id: ID del mapa.
            area_key: Clave única del área.

        Returns:
            Lista de instance_ids de NPCs activos.
        """
        active: list[str] = []
        for instance_id, spawn_info in self._random_spawned_npcs.items():
            if spawn_info["map_id"] == map_id and spawn_info["area_key"] == area_key:
                active.append(instance_id)
        return active

    def get_random_spawn_statistics(self) -> dict[str, Any]:
        """Obtiene estadísticas de random spawns.

        Returns:
            Diccionario con estadísticas.
        """
        return {
            "total_random_spawned": len(self._random_spawned_npcs),
            "configured_maps": len(self._random_spawn_configs),
            "active_respawn_cooldowns": len(self._respawn_cooldowns),
        }
