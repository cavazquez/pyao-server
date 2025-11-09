"""Servicio para gestionar puertas en el mapa."""

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class DoorInfo:
    """Información de una puerta."""

    item_id: int
    name: str
    grh_index: int
    is_open: bool  # False=cerrada, True=abierta
    requires_key: bool  # True si necesita llave
    key_id: int | None  # ID de la llave necesaria (Clave)
    index_open: int | None  # ID del item cuando está abierta
    index_closed: int | None  # ID del item cuando está cerrada
    index_closed_locked: int | None  # ID del item cuando está cerrada con llave


class DoorService:
    """Servicio para gestionar puertas."""

    def __init__(self) -> None:
        """Inicializa el servicio de puertas."""
        self._doors_by_grh: dict[int, DoorInfo] = {}
        self._doors_by_id: dict[int, DoorInfo] = {}
        self._load_doors_catalog()

    def _load_doors_catalog(self) -> None:
        """Carga el catálogo de puertas desde doors.toml."""
        doors_path = (
            Path(__file__).parent.parent.parent.parent / "data/items/world_objects/doors.toml"
        )

        if not doors_path.exists():
            logger.warning("Archivo doors.toml no encontrado en %s", doors_path)
            return

        try:
            with Path(doors_path).open("rb") as f:
                data = tomllib.load(f)

            for item in data.get("item", []):
                # Llave=1 significa que ES una llave (no una puerta)
                # Clave=X significa que requiere la llave con ID X
                is_key_item = item.get("Llave", 0) == 1
                requires_key = item.get("Clave") is not None

                door_info = DoorInfo(
                    item_id=item["id"],
                    name=item.get("Name", "Puerta"),
                    grh_index=item["GrhIndex"],
                    is_open=item.get("Abierta", 1) == 0,  # 0=abierta, 1=cerrada
                    requires_key=requires_key
                    and not is_key_item,  # Requiere llave solo si tiene Clave y no ES una llave
                    key_id=item.get("Clave"),
                    index_open=item.get("IndexAbierta"),
                    index_closed=item.get("IndexCerrada"),
                    index_closed_locked=item.get("IndexCerradaLlave"),
                )

                # Indexar por GrhIndex y por ID
                self._doors_by_grh[door_info.grh_index] = door_info
                self._doors_by_id[door_info.item_id] = door_info

            logger.info("Cargadas %d puertas desde doors.toml", len(self._doors_by_id))

        except Exception:
            logger.exception("Error cargando doors.toml")

    def get_door_by_grh(self, grh_index: int) -> DoorInfo | None:
        """Obtiene información de una puerta por su GrhIndex.

        Args:
            grh_index: GrhIndex de la puerta.

        Returns:
            DoorInfo o None si no existe.
        """
        return self._doors_by_grh.get(grh_index)

    def get_door_by_id(self, item_id: int) -> DoorInfo | None:
        """Obtiene información de una puerta por su ID.

        Args:
            item_id: ID del item.

        Returns:
            DoorInfo o None si no existe.
        """
        return self._doors_by_id.get(item_id)

    @staticmethod
    def toggle_door(door_info: DoorInfo) -> tuple[int, bool]:
        """Alterna el estado de una puerta (abre/cierra).

        Args:
            door_info: Información de la puerta actual.

        Returns:
            Tupla (nuevo_item_id, nuevo_estado_abierta).
        """
        if door_info.is_open:
            # Cerrar puerta
            new_id = door_info.index_closed or door_info.item_id
            return new_id, False
        # Abrir puerta (solo si no requiere llave)
        if door_info.requires_key:
            return door_info.item_id, False  # No se puede abrir

        new_id = door_info.index_open or door_info.item_id
        return new_id, True
