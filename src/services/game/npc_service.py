"""Servicio de NPCs del juego.

Carga y gestiona todos los NPCs (336 totales) desde los archivos TOML
extraídos del cliente, incluyendo hostiles, comerciantes y NPCs especiales.
"""

import logging
import random
from pathlib import Path
from tomllib import load as tomllib_load
from typing import Any

logger = logging.getLogger(__name__)


# Constantes para cálculo de dificultad
EASY_DIFFICULTY_THRESHOLD = 100
MEDIUM_DIFFICULTY_THRESHOLD = 300
HARD_DIFFICULTY_THRESHOLD = 600


class NPCService:
    """Servicio centralizado para manejar el sistema completo de NPCs."""

    def __init__(self, data_dir: Path | None = None) -> None:
        """Inicializa el NPCService.

        Args:
            data_dir: Directorio donde se encuentran los datos TOML de NPCs.
        """
        self.data_dir = data_dir or Path("data")
        self.all_npcs: list[dict[str, Any]] = []
        self.npcs_by_id: dict[int, dict[str, Any]] = {}
        self.npcs_by_name: dict[str, dict[str, Any]] = {}
        self.hostile_npcs: list[dict[str, Any]] = []
        self.trader_npcs: list[dict[str, Any]] = []
        self.npcs_by_category: dict[str, list[dict[str, Any]]] = {}
        self.npcs_by_type: dict[int, list[dict[str, Any]]] = {}
        self.npc_data: dict[str, Any] = {}
        self._load_npc_data()

    def _load_npc_data(self) -> None:
        """Carga los datos de NPCs desde archivos TOML."""
        try:
            # Cargar NPCs completos (usar test data si existe)
            npcs_file = self.data_dir / "test_npcs.toml"
            if not npcs_file.exists():
                npcs_file = self.data_dir / "npcs_complete.toml"

            if npcs_file.exists():
                with npcs_file.open("rb") as f:
                    npcs_data = tomllib_load(f)
                    self.all_npcs = npcs_data.get("npcs_complete", {}).get("npcs", [])

            # Cargar NPCs hostiles (usar test data si existe)
            hostiles_file = self.data_dir / "test_npcs.toml"
            if not hostiles_file.exists():
                hostiles_file = self.data_dir / "npcs_hostiles_extended.toml"

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

            # Cargar NPCs comerciantes (usar test data si existe)
            traders_file = self.data_dir / "test_npcs.toml"
            if not traders_file.exists():
                traders_file = self.data_dir / "npcs_traders_extended.toml"

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

    def _build_indices(self) -> None:
        """Construye índices para búsqueda rápida."""
        # Índice por ID
        self.npcs_by_id = {npc["id"]: npc for npc in self.all_npcs}

        # Índice por nombre (case insensitive)
        self.npcs_by_name = {npc["name"].lower(): npc for npc in self.all_npcs if npc.get("name")}

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
        return self.npcs_by_category.get(category, []).copy()

    def get_npcs_by_type(self, npc_type: int) -> list[dict[str, Any]]:
        """Retorna NPCs de un tipo específico.

        Args:
            npc_type: Tipo de NPC.

        Returns:
            Lista de NPCs del tipo.
        """
        return self.npcs_by_type.get(npc_type, []).copy()

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
            npc_tags = set(npc.get("tags", []))
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

        inventory = npc.get("inventory", {})
        return inventory.get("items", [])

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

        inventory = npc.get("inventory", {})
        return inventory.get("drops", [])

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

        economics = npc.get("economics", {})
        return economics.get("trades", 0) == 1

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

        behavior = npc.get("behavior", {})
        return behavior.get("hostile", 0) == 1

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

        return npc.get("description", "")

    def calculate_npc_difficulty(self, npc: dict[str, Any]) -> str:  # noqa: PLR6301
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

        return random.choice(npcs_in_category)  # noqa: S311

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

        return random.choice(npcs_in_range)  # noqa: S311

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
            location_type: Tipo de ubicación (ciudad, mazmorra, etc.)

        Returns:
            Lista de NPCs del tipo de ubicación.
        """
        # Mapeo de categorías a tipos de ubicación
        location_mapping = {
            "ciudad": ["NPCS ULLATHORPE", "NPCS NIX", "NPCS BANDERBILL", "NPCS LINDOS"],
            "guardias": ["NPCS GUARDIAS ARMADA", "NPCS GUARDIAS LEGIÓN"],
            "hostiles": ["NPCS HOSTILES", "NPCS PRETORIANOS"],
            "comerciantes": ["NPCS COMERCIANTES"],
            "entrenadores": ["NPCS ENTRENADORES"],
            "resucitadores": ["NPCS RESUCITADORES"],
        }

        categories = location_mapping.get(location_type.lower, [])
        matching_npcs = []

        for category in categories:
            matching_npcs.extend(self.get_npcs_by_category(category))

        return matching_npcs

    def get_npc_statistics(self) -> dict[str, Any]:
        """Retorna estadísticas sobre los NPCs cargados.

        Returns:
            Diccionario con estadísticas.
        """
        stats = {
            "total_npcs": len(self.all_npcs),
            "hostile_npcs": len(self.hostile_npcs),
            "trader_npcs": len(self.trader_npcs),
            "combat_npcs": len(
                [npc for npc in self.all_npcs if npc.get("combat", {}).get("exp_given", 0) > 0]
            ),
            "categories": {},
            "types": {},
            "npcs_by_difficulty": {"Fácil": 0, "Medio": 0, "Difícil": 0, "Extremo": 0},
        }

        # Estadísticas por categoría
        for category, npcs in self.npcs_by_category.items():
            stats["categories"][category] = len(npcs)

        # Estadísticas por tipo
        for npc_type, npcs in self.npcs_by_type.items():
            stats["types"][npc_type] = len(npcs)

        # Estadísticas por dificultad
        for npc in self.all_npcs:
            difficulty = self.calculate_npc_difficulty(npc)
            stats["npcs_by_difficulty"][difficulty] += 1

        return stats


# Instancia global del servicio
_npc_service: NPCService | None = None


def get_npc_service() -> NPCService:
    """Retorna la instancia global del servicio de NPCs.

    Returns:
        Instancia global del NPCService.
    """
    global _npc_service
    if _npc_service is None:
        _npc_service = NPCService()
    return _npc_service


def initialize_npc_service(data_dir: Path | None = None) -> None:
    """Inicializa el servicio global de NPCs."""
    global _npc_service
    _npc_service = NPCService(data_dir)
