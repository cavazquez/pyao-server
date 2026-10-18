"""Estado de suelo compatible con JSON legado e identidad estable versionada por stack."""

import json
import re
from hashlib import sha256
from typing import cast

from src.models.item_constants import GOLD_ITEM_ID, MAX_PLAYER_GOLD
from src.utils.slot_plan import MAX_SLOT_QUANTITY

GroundItem = dict[str, int | str | None]
GROUND_TTL_SECONDS = 3600
MAX_GROUND_ITEMS_PER_TILE = 10
MAX_GROUND_COORDINATE = 100
MAX_GROUND_MAP_ID = 290
COORDINATE_PARTS = 2
_STACK_ID = re.compile(r"^g1\.[0-9a-f]{32}$")


def stack_identity(identity: str) -> str:
    """Deriva un identificador estable de una operación, sin exponer datos del jugador.

    Returns:
        Identificador con versión g1 y nonce resumido.
    """
    return "g1." + sha256(identity.encode()).hexdigest()[:32]


def validate_item(item: GroundItem) -> None:
    """Valida cantidades y campos que intervienen en transferencias.

    Raises:
        ValueError: Si un objeto persistido no puede transferirse sin corrupción.
    """
    item_id, quantity = item.get("item_id"), item.get("quantity")
    limit = MAX_PLAYER_GOLD if item_id == GOLD_ITEM_ID else MAX_SLOT_QUANTITY
    if type(item_id) is not int or not 1 <= item_id <= MAX_SLOT_QUANTITY:
        msg = "Objeto del suelo inválido"
        raise ValueError(msg)
    if type(quantity) is not int or not 1 <= quantity <= limit:
        msg = "Cantidad del suelo inválida"
        raise ValueError(msg)
    if not isinstance(item.get("stack_id"), str) or not _STACK_ID.fullmatch(str(item["stack_id"])):
        msg = "Identidad del stack inválida"
        raise ValueError(msg)


class GroundState:
    """Copia de un mapa; derive IDs legacy al leer sin hacer escrituras de migración."""

    def __init__(self, map_id: int, raw: str | None) -> None:
        """Carga JSON y preserva campos; no modifica Redis al adoptar IDs legacy.

        Raises:
            ValueError: Ante JSON, coordenadas, identidad o cantidades corruptos.
            TypeError: Si la estructura persistida no es un mapa de listas de objetos.
        """
        if type(map_id) is not int or not 1 <= map_id <= MAX_GROUND_MAP_ID:
            msg = "Mapa del suelo inválido"
            raise ValueError(msg)
        data = json.loads(raw) if raw else {}
        if not isinstance(data, dict):
            msg = "Estado del suelo inválido"
            raise TypeError(msg)
        self.tiles: dict[str, list[GroundItem]] = {}
        identities: set[str] = set()
        for coordinate, values in data.items():
            parts = coordinate.split(",") if isinstance(coordinate, str) else []
            if len(parts) != COORDINATE_PARTS or not all(
                p.isdigit() and 1 <= int(p) <= MAX_GROUND_COORDINATE for p in parts
            ):
                msg = "Coordenada del suelo inválida"
                raise ValueError(msg)
            if not isinstance(values, list):
                msg = "Lista de objetos del suelo inválida"
                raise TypeError(msg)
            self.tiles[coordinate] = []
            for index, original in enumerate(values):
                if not isinstance(original, dict):
                    msg = "Objeto persistido inválido"
                    raise TypeError(msg)
                item = cast("GroundItem", original.copy())
                if "stack_id" not in item:
                    legacy = json.dumps([map_id, coordinate, index, original], sort_keys=True)
                    item["stack_id"] = stack_identity(legacy)
                validate_item(item)
                if str(item["stack_id"]) in identities:
                    msg = "Identidad del suelo duplicada"
                    raise ValueError(msg)
                identities.add(str(item["stack_id"]))
                self.tiles[coordinate].append(item)

    def tile(self, x: int, y: int) -> list[GroundItem]:
        """Obtiene el tile de la copia local.

        Returns:
            Lista de stacks de la posición.
        """
        return self.tiles.get(f"{x},{y}", [])

    def append(self, x: int, y: int, item: GroundItem) -> None:
        """Agrega un stack completo o rechaza la capacidad del tile.

        Raises:
            ValueError: Si no entra el objeto o su identidad ya existe.
        """
        if (
            type(x) is not int
            or type(y) is not int
            or not 1 <= x <= MAX_GROUND_COORDINATE
            or not 1 <= y <= MAX_GROUND_COORDINATE
        ):
            msg = "Coordenada del suelo inválida"
            raise ValueError(msg)
        validate_item(item)
        if any(
            existing["stack_id"] == item["stack_id"]
            for row in self.tiles.values()
            for existing in row
        ):
            msg = "El objeto ya está en el suelo"
            raise ValueError(msg)
        coordinate = f"{x},{y}"
        if len(self.tiles.get(coordinate, [])) >= MAX_GROUND_ITEMS_PER_TILE:
            msg = "No hay espacio en el suelo de este lugar"
            raise ValueError(msg)
        self.tiles.setdefault(coordinate, []).append(item.copy())

    def encode(self) -> str:
        """Serializa el mapa compatible con lectores JSON anteriores.

        Returns:
            Objeto por coordenadas con un campo opcional stack_id en cada fila.
        """
        return json.dumps(self.tiles, ensure_ascii=True, separators=(",", ":"))

    def positions(self) -> dict[tuple[int, int], list[GroundItem]]:
        """Convierte coordenadas al formato del índice de mapas.

        Returns:
            Mapa de posiciones sin modificar el estado persistido.
        """
        return {
            cast("tuple[int, int]", tuple(map(int, coordinate.split(",")))): values
            for coordinate, values in self.tiles.items()
            if values
        }
