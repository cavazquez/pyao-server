"""Servicio para manejar loot tables de NPCs."""

import logging
import random
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class LootItem:
    """Representa un item en una loot table."""

    item_id: int
    probability: float  # 0.0 a 1.0
    min_quantity: int
    max_quantity: int


@dataclass
class LootTable:
    """Tabla de loot para un NPC."""

    npc_id: int
    name: str
    items: list[LootItem]


class LootTableService:
    """Servicio que maneja las loot tables de NPCs."""

    def __init__(self, loot_tables_path: str = "data/loot_tables.toml") -> None:
        """Inicializa el servicio de loot tables.

        Args:
            loot_tables_path: Ruta al archivo loot_tables.toml.
        """
        self._loot_tables: dict[int, LootTable] = {}
        self._loot_tables_path = loot_tables_path
        self._load_loot_tables()

    def _load_loot_tables(self) -> None:
        """Carga las loot tables desde el archivo TOML."""
        try:
            path = Path(self._loot_tables_path)
            if not path.exists():
                logger.warning("Archivo de loot tables no encontrado: %s", self._loot_tables_path)
                return

            with path.open("rb") as f:
                data = tomllib.load(f)

            if "loot_table" not in data:
                logger.warning(
                    "No se encontró la sección [loot_table] en %s", self._loot_tables_path
                )
                return

            for table_data in data["loot_table"]:
                npc_id = table_data.get("id")
                if npc_id is None:
                    logger.warning("Loot table sin npc_id encontrada, ignorando: %s", table_data)
                    continue

                # Parsear items de la loot table
                items: list[LootItem] = []
                for item_data in table_data.get("items", []):
                    item = LootItem(
                        item_id=item_data["item_id"],
                        probability=float(item_data.get("probability", 1.0)),
                        min_quantity=item_data.get("min_quantity", 1),
                        max_quantity=item_data.get("max_quantity", 1),
                    )
                    items.append(item)

                loot_table = LootTable(
                    npc_id=npc_id,
                    name=table_data.get("name", f"NPC {npc_id}"),
                    items=items,
                )

                self._loot_tables[npc_id] = loot_table
                logger.debug(
                    "Loot table cargada: NPC %d - %s (%d items)",
                    npc_id,
                    loot_table.name,
                    len(items),
                )

            logger.info("Loot tables cargadas: %d NPCs", len(self._loot_tables))

        except Exception:
            logger.exception("Error al cargar loot tables desde %s", self._loot_tables_path)

    def get_loot_for_npc(self, npc_id: int) -> list[tuple[int, int]]:
        """Genera loot para un NPC según su loot table.

        Args:
            npc_id: ID del NPC.

        Returns:
            Lista de tuplas (item_id, quantity) con los items dropeados.
        """
        loot_table = self._loot_tables.get(npc_id)
        if not loot_table:
            logger.debug("No hay loot table para NPC %d", npc_id)
            return []

        loot: list[tuple[int, int]] = []

        for loot_item in loot_table.items:
            # Tirar dado para ver si dropea este item
            if random.random() <= loot_item.probability:  # noqa: S311
                # Calcular cantidad aleatoria
                quantity = random.randint(loot_item.min_quantity, loot_item.max_quantity)  # noqa: S311
                loot.append((loot_item.item_id, quantity))
                logger.debug(
                    "NPC %d dropea: item_id=%d quantity=%d (prob=%.2f)",
                    npc_id,
                    loot_item.item_id,
                    quantity,
                    loot_item.probability,
                )

        return loot

    def has_loot_table(self, npc_id: int) -> bool:
        """Verifica si un NPC tiene loot table configurada.

        Args:
            npc_id: ID del NPC.

        Returns:
            True si tiene loot table, False si no.
        """
        return npc_id in self._loot_tables

    def get_loot_table(self, npc_id: int) -> LootTable | None:
        """Obtiene la loot table de un NPC.

        Args:
            npc_id: ID del NPC.

        Returns:
            LootTable o None si no existe.
        """
        return self._loot_tables.get(npc_id)
