"""Catálogo de items del juego."""

import tomllib
from pathlib import Path

from src.item import Item, ItemType
from src.item_types import ObjType


def _load_items_from_toml() -> dict[int, Item]:
    """Carga todos los items desde el archivo items.toml.

    Returns:
        Diccionario con todos los items indexados por ID.
    """
    toml_path = Path(__file__).parent.parent / "data" / "items.toml"

    with Path(toml_path).open("rb") as f:
        data = tomllib.load(f)

    items = {}

    for item_data in data.get("item", []):
        item_id = item_data.get("id")
        if not item_id:
            continue

        # Mapear ObjType a ItemType
        obj_type = item_data.get("ObjType", 0)
        item_type = _map_obj_type_to_item_type(obj_type)

        # Crear item básico con datos del TOML
        items[item_id] = Item(
            item_id=item_id,
            name=item_data.get("Name", f"Item {item_id}"),
            item_type=item_type,
            graphic_id=item_data.get("GrhIndex", 0),
            stackable=obj_type
            in {
                ObjType.COMIDA,
                ObjType.POCIONES,
                ObjType.BEBIDA,
                ObjType.LENA,
                ObjType.DINERO,
                ObjType.FLECHAS,
            },
            max_stack=99,
            consumable=obj_type in {ObjType.COMIDA, ObjType.POCIONES, ObjType.BEBIDA},
            equippable=obj_type
            in {ObjType.ARMAS, ObjType.ARMADURAS, ObjType.ESCUDOS, ObjType.CASCOS, ObjType.ANILLOS},
            value=item_data.get("Valor", 0),
            min_damage=item_data.get("MinHit"),
            max_damage=item_data.get("MaxHit"),
            defense=item_data.get("MinDef"),
            restore_hp=(
                int(item_data.get("MaxModificador", 0))
                if item_data.get("TipoPocion") == 3  # noqa: PLR2004
                else 0
            ),
            restore_mana=(
                int(item_data.get("MaxModificador", 0))
                if item_data.get("TipoPocion") == 4  # noqa: PLR2004
                else 0
            ),
            restore_hunger=item_data.get("MinHAM"),
            restore_thirst=item_data.get("MinAgu"),
        )

    return items


def _map_obj_type_to_item_type(obj_type: int) -> ItemType:
    """Mapea ObjType del TOML a ItemType de Python.

    Args:
        obj_type: Tipo de objeto del TOML.

    Returns:
        ItemType correspondiente.
    """
    mapping: dict[int, ItemType] = {
        ObjType.COMIDA: ItemType.FOOD,
        ObjType.ARMAS: ItemType.WEAPON,
        ObjType.ARMADURAS: ItemType.ARMOR,
        ObjType.POCIONES: ItemType.POTION,
        ObjType.BEBIDA: ItemType.FOOD,
        ObjType.ESCUDOS: ItemType.SHIELD,
        ObjType.CASCOS: ItemType.HELMET,
        ObjType.ANILLOS: ItemType.MISC,  # Los anillos se mapean como MISC por ahora
    }
    return mapping.get(obj_type, ItemType.MISC)


# Catálogo de items disponibles
# NOTA: Los IDs y graphic_id corresponden al archivo obj.dat del cliente VB6
# Se cargan automáticamente desde data/items.toml
ITEMS_CATALOG: dict[int, Item] = _load_items_from_toml()

# Catálogo manual (deprecated - usar items.toml)
_MANUAL_ITEMS_CATALOG: dict[int, Item] = {
    # Comida (IDs 1, 21-29 del obj.dat)
    1: Item(
        item_id=1,
        name="Manzana Roja",
        item_type=ItemType.FOOD,
        graphic_id=506,  # GrhIndex del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=2,
        restore_hunger=10,  # MinHAM=10
    ),
    # Pociones (IDs 36-39 del obj.dat original)
    36: Item(
        item_id=36,
        name="Poción Amarilla",
        item_type=ItemType.POTION,
        graphic_id=540,  # GrhIndex del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=120,
        # TipoPocion=1: Modifica Agilidad (MinModificador=3, MaxModificador=5, DuracionEfecto=1000)
    ),
    37: Item(
        item_id=37,
        name="Poción Azul",
        item_type=ItemType.POTION,
        graphic_id=541,  # GrhIndex del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=25,
        restore_mana=16,  # Promedio de MinModificador=12, MaxModificador=20
    ),
    38: Item(
        item_id=38,
        name="Poción Roja",
        item_type=ItemType.POTION,
        graphic_id=542,  # GrhIndex del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=20,
        restore_hp=30,  # MinModificador=30, MaxModificador=30
    ),
    39: Item(
        item_id=39,
        name="Poción Verde",
        item_type=ItemType.POTION,
        graphic_id=543,  # GrhIndex del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=180,
        # TipoPocion=2: Modifica Fuerza (MinModificador=2, MaxModificador=6, DuracionEfecto=1000)
    ),
    # Comida
    3: Item(
        item_id=3,
        name="Manzana",
        item_type=ItemType.FOOD,
        graphic_id=3,  # Ajustar según gráficos del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=5,
        restore_hunger=20,
    ),
    4: Item(
        item_id=4,
        name="Agua",
        item_type=ItemType.FOOD,
        graphic_id=4,  # Ajustar según gráficos del cliente
        stackable=True,
        max_stack=99,
        consumable=True,
        value=5,
        restore_thirst=20,
    ),
    # Armas
    10: Item(
        item_id=10,
        name="Espada Corta",
        item_type=ItemType.WEAPON,
        graphic_id=5,  # Ajustar según gráficos del cliente
        equippable=True,
        value=100,
        min_damage=5,
        max_damage=10,
    ),
    11: Item(
        item_id=11,
        name="Daga",
        item_type=ItemType.WEAPON,
        graphic_id=6,  # Ajustar según gráficos del cliente
        equippable=True,
        value=50,
        min_damage=3,
        max_damage=7,
    ),
    # Armaduras
    20: Item(
        item_id=20,
        name="Armadura de Cuero",
        item_type=ItemType.ARMOR,
        graphic_id=7,  # Ajustar según gráficos del cliente
        equippable=True,
        value=150,
        defense=5,
    ),
    21: Item(
        item_id=21,
        name="Túnica",
        item_type=ItemType.ARMOR,
        graphic_id=8,  # Ajustar según gráficos del cliente
        equippable=True,
        value=75,
        defense=3,
    ),
    # Cascos
    30: Item(
        item_id=30,
        name="Casco de Hierro",
        item_type=ItemType.HELMET,
        graphic_id=9,  # Ajustar según gráficos del cliente
        equippable=True,
        value=100,
        defense=3,
    ),
    # Escudos
    40: Item(
        item_id=40,
        name="Escudo de Madera",
        item_type=ItemType.SHIELD,
        graphic_id=10,  # Ajustar según gráficos del cliente
        equippable=True,
        value=80,
        defense=4,
    ),
}


def get_item(item_id: int) -> Item | None:
    """Obtiene un item del catálogo.

    Args:
        item_id: ID del item.

    Returns:
        Item si existe, None si no.
    """
    return ITEMS_CATALOG.get(item_id)


def get_all_items() -> list[Item]:
    """Obtiene todos los items del catálogo.

    Returns:
        Lista de todos los items.
    """
    return list(ITEMS_CATALOG.values())
