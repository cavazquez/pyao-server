"""Servicio de NPCs del juego.

Carga y gestiona todos los NPCs (336 totales) desde los archivos TOML
extraídos del cliente, incluyendo hostiles, comerciantes y NPCs especiales.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from tomllib import load as tomllib_load
from typing import Any, ClassVar, cast

logger = logging.getLogger(__name__)


# Constantes para cálculo de dificultad
EASY_DIFFICULTY_THRESHOLD = 100
MEDIUM_DIFFICULTY_THRESHOLD = 300
HARD_DIFFICULTY_THRESHOLD = 600


class NPCService:
    """Servicio para gestión de NPCs."""

    _instance: ClassVar[NPCService | None] = None

    def __init__(self, data_dir: Path | None = None) -> None:
        """Inicializa el NPCService.

        Args:
            data_dir: Directorio donde se encuentran los datos TOML de NPCs.
        """
        if getattr(self, "_initialized", False):
            return

        self.data_dir = data_dir or Path("data")
        self.all_npcs: list[dict[str, Any]] = []
        self.npcs_by_id: dict[int, dict[str, Any]] = {}
        self.npcs_by_name: dict[str, dict[str, Any]] = {}
        self.hostile_npcs: list[dict[str, Any]] = []
        self.trader_npcs: list[dict[str, Any]] = []
        self.npcs_by_category: dict[str, list[dict[str, Any]]] = {}
        self.npcs_by_type: dict[int, list[dict[str, Any]]] = {}
        self.npc_data: dict[str, Any] = {}
        self._initialized = False

        # Cargar datos de NPCs inmediatamente
        self.load_npc_data()

    def load_npc_data(self) -> None:
        """Carga datos de NPCs desde archivos TOML."""
        try:
            # Cargar NPCs completos desde data/npcs/complete.toml
            npcs_file = self.data_dir / "npcs" / "complete.toml"

            if npcs_file.exists():
                with npcs_file.open("rb") as f:
                    npcs_data = tomllib_load(f)
                    self.all_npcs = npcs_data.get("npcs_complete", {}).get("npcs", [])

            # Cargar NPCs hostiles desde data/npcs/hostiles.toml
            hostiles_file = self.data_dir / "npcs" / "hostiles.toml"

            if hostiles_file.exists():
                with hostiles_file.open("rb") as f:
                    hostiles_data = tomllib_load(f)
                    # Usar npcs_hostiles si existe, sino filtrar de todos
                    if "npcs_hostiles" in hostiles_data:
                        self.hostile_npcs = hostiles_data.get("npcs_hostiles", {}).get("npcs", [])
                    else:
                        self.hostile_npcs = [
                            npc
                            for npc in self.all_npcs
                            if npc.get("behavior", {}).get("hostile", 0) == 1
                        ]

            # Cargar NPCs comerciantes desde data/npcs/traders.toml
            traders_file = self.data_dir / "npcs" / "traders.toml"

            if traders_file.exists():
                with traders_file.open("rb") as f:
                    traders_data = tomllib_load(f)
                    # Usar npcs_traders si existe, sino filtrar de todos
                    if "npcs_traders" in traders_data:
                        self.trader_npcs = traders_data.get("npcs_traders", {}).get("npcs", [])
                    else:
                        self.trader_npcs = [
                            npc
                            for npc in self.all_npcs
                            if npc.get("economics", {}).get("trades", 0) == 1
                        ]

            # Cargar NPCs amigables desde data/npcs/friendly.toml
            amigables_file = self.data_dir / "npcs" / "friendly.toml"
            if amigables_file.exists():
                with amigables_file.open("rb") as f:
                    amigables_data = tomllib_load(f)
                    amigables_npcs = amigables_data.get("npc", [])
                    # Agregar NPCs amigables a la lista general
                    self.all_npcs.extend(amigables_npcs)
                    # Agregar comerciantes
                    for npc in amigables_npcs:
                        if npc.get("es_mercader", False):
                            self.trader_npcs.append(npc)

            # Construir índices
            self._build_indices()

            self.npc_data = {
                "all": self.all_npcs,
                "hostiles": self.hostile_npcs,
                "traders": self.trader_npcs,
                "by_category": self.npcs_by_category,
                "by_type": self.npcs_by_type,
            }

            logger.info(
                "NPCs cargados: %d totales, %d hostiles, %d comerciantes",
                len(self.all_npcs),
                len(self.hostile_npcs),
                len(self.trader_npcs),
            )

        except Exception:
            logger.exception("Error cargando datos de NPCs")

        self._initialized = True

    @staticmethod
    def _load_spawn_entries(spawns_path: Path) -> list[dict[str, Any]] | None:
        """Carga entradas de spawn desde un archivo TOML.

        Returns:
            Lista de entradas de spawn o ``None`` si ocurre un error.
        """
        if not spawns_path.exists():
            logger.warning("Archivo de spawns no encontrado: %s", spawns_path)
            return None

        try:
            with spawns_path.open("rb") as file:
                data = tomllib_load(file)
        except Exception:
            logger.exception("Error al leer archivo de spawns %s", spawns_path)
            return None

        spawn_entries = data.get("spawn", [])
        if not isinstance(spawn_entries, list) or not spawn_entries:
            logger.warning("No se encontró la sección [spawn] en %s", spawns_path)
            return None

        return cast("list[dict[str, Any]]", spawn_entries)

    def spawn_npc(
        self, npc_id: int, map_id: int, x: int, y: int, heading: int
    ) -> dict[str, Any] | None:
        """Spawnea un NPC en el mapa.

        Args:
            npc_id: ID del NPC.
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
            heading: Dirección del NPC.

        Returns:
            NPC spawneado o ``None`` si no se pudo crear.
        """
        npc_template = self.get_npc_by_id(npc_id)
        if npc_template is None:
            logger.warning("Intento de spawn para NPC desconocido id=%s", npc_id)
            return None

        npc_instance: dict[str, Any] = {
            "id": npc_id,
            "map": map_id,
            "x": x,
            "y": y,
            "heading": heading,
        }
        logger.debug(
            "NPC template %s preparado para spawn en mapa %d (%d,%d)",
            npc_template.get("name", "desconocido"),
            map_id,
            x,
            y,
        )
        return npc_instance

    def _build_indices(self) -> None:
        """Construye índices para búsqueda rápida."""
        # Índice por ID
        self.npcs_by_id = {npc["id"]: npc for npc in self.all_npcs}

        # Índice por nombre (case insensitive) - soporta tanto "name" como "nombre"
        self.npcs_by_name = {}
        for npc in self.all_npcs:
            name = npc.get("nombre") or npc.get("name")
            if name:
                self.npcs_by_name[name.lower()] = npc

        # Índice por categoría
        self.npcs_by_category = {}
        for npc in self.all_npcs:
            category = npc.get("category", "NPCS VARIOS")
            if category not in self.npcs_by_category:
                self.npcs_by_category[category] = []
            self.npcs_by_category[category].append(npc)

        # Índice por tipo
        self.npcs_by_type = {}
        for npc in self.all_npcs:
            npc_type = npc.get("npc_type", 0)
            if npc_type not in self.npcs_by_type:
                self.npcs_by_type[npc_type] = []
            self.npcs_by_type[npc_type].append(npc)

    def get_all_npcs(self) -> list[dict[str, Any]]:
        """Retorna todos los NPCs disponibles.

        Returns:
            Lista completa de todos los NPCs.
        """
        return self.all_npcs.copy()

    def get_npc_by_id(self, npc_id: int) -> dict[str, Any] | None:
        """Busca un NPC por su ID.

        Args:
            npc_id: ID del NPC a buscar.

        Returns:
            NPC encontrado o None si no existe.
        """
        return self.npcs_by_id.get(npc_id)

    def get_npc_by_name(self, name: str) -> dict[str, Any] | None:
        """Busca un NPC por su nombre.

        Args:
            name: Nombre del NPC a buscar (case insensitive).

        Returns:
            NPC encontrado o None si no existe.
        """
        return self.npcs_by_name.get(name.lower())

    def get_hostile_npcs(self) -> list[dict[str, Any]]:
        """Retorna todos los NPCs hostiles.

        Returns:
            Lista de NPCs hostiles.
        """
        return self.hostile_npcs.copy()

    def get_trader_npcs(self) -> list[dict[str, Any]]:
        """Retorna todos los NPCs comerciantes.

        Returns:
            Lista de NPCs comerciantes.
        """
        return self.trader_npcs.copy()

    def get_npcs_by_category(self, category: str) -> list[dict[str, Any]]:
        """Retorna NPCs de una categoría específica.

        Args:
            category: Categoría de NPCs.

        Returns:
            Lista de NPCs de la categoría.
        """
        npcs = self.npcs_by_category.get(category)
        if npcs is None:
            return []
        return npcs.copy()

    def get_npcs_by_type(self, npc_type: int) -> list[dict[str, Any]]:
        """Retorna NPCs de un tipo específico.

        Args:
            npc_type: Tipo de NPC.

        Returns:
            Lista de NPCs del tipo.
        """
        npcs = self.npcs_by_type.get(npc_type)
        if npcs is None:
            return []
        return npcs.copy()

    def get_npcs_by_level_range(self, min_level: int, max_level: int) -> list[dict[str, Any]]:
        """Retorna NPCs dentro de un rango de nivel (basado en HP).

        Args:
            min_level: Nivel mínimo.
            max_level: Nivel máximo.

        Returns:
            Lista de NPCs en el rango.
        """
        npcs_in_range = []

        for npc in self.all_npcs:
            combat = npc.get("combat", {})
            max_hp = combat.get("max_hp", 0)

            # Estimar nivel basado en HP (regla simple: nivel ≈ HP/10)
            estimated_level = max_hp // 10

            if min_level <= estimated_level <= max_level:
                npcs_in_range.append(npc)

        return npcs_in_range

    def get_npcs_by_tags(self, tags: list[str]) -> list[dict[str, Any]]:
        """Retorna NPCs que contengan todos los tags especificados.

        Args:
            tags: Lista de tags a buscar.

        Returns:
            Lista de NPCs con los tags.
        """
        matching_npcs = []

        for npc in self.all_npcs:
            raw_tags = npc.get("tags", [])
            if not isinstance(raw_tags, list):
                continue
            npc_tags = {str(tag) for tag in raw_tags}
            if all(tag in npc_tags for tag in tags):
                matching_npcs.append(npc)

        return matching_npcs

    def get_npc_inventory(self, npc_id: int) -> list[dict[str, Any]]:
        """Retorna el inventario de un NPC.

        Args:
            npc_id: ID del NPC.

        Returns:
            Lista de items en el inventario.
        """
        npc = self.get_npc_by_id(npc_id)
        if not npc:
            return []

        inventory = npc.get("inventory")
        if not isinstance(inventory, dict):
            return []
        items = inventory.get("items")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    def get_npc_drops(self, npc_id: int) -> list[dict[str, Any]]:
        """Retorna los drops de un NPC.

        Args:
            npc_id: ID del NPC.

        Returns:
            Lista de posibles drops.
        """
        npc = self.get_npc_by_id(npc_id)
        if not npc:
            return []

        inventory = npc.get("inventory")
        if not isinstance(inventory, dict):
            return []
        drops = inventory.get("drops")
        if not isinstance(drops, list):
            return []
        return [drop for drop in drops if isinstance(drop, dict)]

    def can_npc_trade(self, npc_id: int) -> bool:
        """Verifica si un NPC puede comerciar.

        Args:
            npc_id: ID del NPC.

        Returns:
            True si puede comerciar.
        """
        npc = self.get_npc_by_id(npc_id)
        if not npc:
            return False

        # Verificar formato economics.trades (nuevo)
        economics = npc.get("economics")
        if isinstance(economics, dict):
            trades_value = economics.get("trades", 0)
            if bool(trades_value):
                return True

        # Verificar formato es_mercader (amigables)
        es_mercader = npc.get("es_mercader", False)
        return bool(es_mercader)

    def is_npc_hostile(self, npc_id: int) -> bool:
        """Verifica si un NPC es hostil.

        Args:
            npc_id: ID del NPC.

        Returns:
            True si es hostil.
        """
        npc = self.get_npc_by_id(npc_id)
        if not npc:
            return False

        behavior = npc.get("behavior")
        if not isinstance(behavior, dict):
            return False
        return bool(behavior.get("hostile", 0))

    def get_npc_dialog(self, npc_id: int) -> str:
        """Retorna el diálogo principal de un NPC.

        Args:
            npc_id: ID del NPC.

        Returns:
            Diálogo del NPC o vacío si no tiene.
        """
        npc = self.get_npc_by_id(npc_id)
        if not npc:
            return ""

        description = npc.get("description", "")
        return description if isinstance(description, str) else ""

    def calculate_npc_difficulty(self, npc: dict[str, Any]) -> str:
        """Calcula la dificultad de un NPC.

        Args:
            npc: Datos del NPC.

        Returns:
            String de dificultad (Fácil, Medio, Difícil, Extremo).
        """
        combat = npc.get("combat", {})
        max_hp = combat.get("max_hp", 0)
        attack_power = combat.get("attack_power", 0)
        defense = combat.get("defense", 0)

        # Calcular poder de combate
        combat_power = max_hp + (attack_power * 5) + (defense * 3)

        if combat_power < EASY_DIFFICULTY_THRESHOLD:
            return "Fácil"
        if combat_power < MEDIUM_DIFFICULTY_THRESHOLD:
            return "Medio"
        if combat_power < HARD_DIFFICULTY_THRESHOLD:
            return "Difícil"
        return "Extremo"

    def get_random_npc_by_category(self, category: str) -> dict[str, Any] | None:
        """Retorna un NPC aleatorio de una categoría.

        Args:
            category: Categoría del NPC.

        Returns:
            NPC aleatorio o None si no hay NPCs.
        """
        npcs_in_category = self.get_npcs_by_category(category)
        if not npcs_in_category:
            return None

        return random.choice(npcs_in_category)

    def get_random_npc_by_level(
        self, target_level: int, variance: int = 5
    ) -> dict[str, Any] | None:
        """Retorna un NPC aleatorio de un nivel específico.

        Args:
            target_level: Nivel objetivo.
            variance: Variación permitida del nivel.

        Returns:
            NPC aleatorio o None si no hay NPCs.
        """
        min_level = max(1, target_level - variance)
        max_level = target_level + variance

        npcs_in_range = self.get_npcs_by_level_range(min_level, max_level)
        if not npcs_in_range:
            return None

        return random.choice(npcs_in_range)

    def search_npcs(self, query: str) -> list[dict[str, Any]]:
        """Busca NPCs por nombre o descripción.

        Args:
            query: Texto a buscar (case insensitive).

        Returns:
            Lista de NPCs que coinciden.
        """
        query = query.lower()
        matching_npcs = []

        for npc in self.all_npcs:
            # Buscar en nombre
            name = npc.get("name", "").lower()
            if query in name:
                matching_npcs.append(npc)
                continue

            # Buscar en descripción
            description = npc.get("description", "").lower()
            if query in description:
                matching_npcs.append(npc)
                continue

            # Buscar en comentario
            comment = npc.get("comment", "").lower()
            if query in comment:
                matching_npcs.append(npc)

        return matching_npcs

    def get_npcs_by_location_type(self, location_type: str) -> list[dict[str, Any]]:
        """Retorna NPCs por tipo de ubicación (basado en categoría).

        Args:
            location_type: Tipo de ubicación (ciudad, mazmorra, etc.).

        Returns:
            Lista de NPCs del tipo de ubicación.
        """
        # Mapeo de categorías a tipos de ubicación
        location_mapping: dict[str, list[str]] = {
            "ciudad": ["NPCS ULLATHORPE", "NPCS NIX", "NPCS BANDERBILL", "NPCS LINDOS"],
            "guardias": ["NPCS GUARDIAS ARMADA", "NPCS GUARDIAS LEGIÓN"],
            "hostiles": ["NPCS HOSTILES", "NPCS PRETORIANOS"],
            "comerciantes": ["NPCS COMERCIANTES"],
            "entrenadores": ["NPCS ENTRENADORES"],
            "resucitadores": ["NPCS RESUCITADORES"],
        }

        categories = location_mapping.get(location_type.lower(), [])
        matching_npcs = []

        for category in categories:
            matching_npcs.extend(self.get_npcs_by_category(category))

        return matching_npcs

    def get_npc_statistics(self) -> dict[str, Any]:
        """Retorna estadísticas sobre los NPCs cargados.

        Returns:
            Diccionario con estadísticas.
        """
        combat_npcs = [
            npc for npc in self.all_npcs if npc.get("combat", {}).get("exp_given", 0) > 0
        ]

        categories_stats: dict[str, int] = {
            category: len(npcs) for category, npcs in self.npcs_by_category.items()
        }
        types_stats: dict[int, int] = {
            npc_type: len(npcs) for npc_type, npcs in self.npcs_by_type.items()
        }
        difficulty_stats: dict[str, int] = {"Fácil": 0, "Medio": 0, "Difícil": 0, "Extremo": 0}
        for npc in self.all_npcs:
            difficulty = self.calculate_npc_difficulty(npc)
            difficulty_stats[difficulty] += 1

        return {
            "total_npcs": len(self.all_npcs),
            "hostile_npcs": len(self.hostile_npcs),
            "trader_npcs": len(self.trader_npcs),
            "combat_npcs": len(combat_npcs),
            "categories": categories_stats,
            "types": types_stats,
            "npcs_by_difficulty": difficulty_stats,
        }

    @classmethod
    def get_instance(cls, data_dir: Path | None = None) -> NPCService:
        """Obtiene la instancia singleton del servicio.

        Returns:
            Instancia única de ``NPCService``.
        """
        if cls._instance is None:
            cls._instance = cls(data_dir=data_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia la instancia singleton."""
        cls._instance = None


def get_npc_service() -> NPCService:
    """Retorna la instancia singleton del NPCService.

    Returns:
        Instancia singleton del NPCService.
    """
    return NPCService.get_instance()


def initialize_npc_service(data_dir: Path | None = None) -> NPCService:
    """Inicializa el servicio singleton con directorio personalizado.

    Args:
        data_dir: Directorio donde se encuentran los datos.

    Returns:
        Instancia del NPCService.
    """
    NPCService.reset_instance()
    return NPCService.get_instance(data_dir=data_dir)
