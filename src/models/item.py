"""Modelo de datos para items del juego."""

from dataclasses import dataclass
from enum import Enum

from src.models.item_types import ObjType


class ItemType(Enum):
    """Tipos de items."""

    WEAPON = "weapon"
    ARMOR = "armor"
    HELMET = "helmet"
    SHIELD = "shield"
    ACCESSORY = "accessory"
    POTION = "potion"
    FOOD = "food"
    MISC = "misc"

    def to_client_type(self) -> int:
        """Convierte el tipo de item a un número para el cliente.

        Returns:
            Número de tipo para el protocolo del cliente.
        """
        # Mapeo de tipos a números del protocolo AO
        type_map = {
            ItemType.WEAPON: ObjType.ARMAS,
            ItemType.ARMOR: ObjType.ARMADURAS,
            ItemType.HELMET: ObjType.CASCOS,
            ItemType.SHIELD: ObjType.ESCUDOS,
            ItemType.ACCESSORY: ObjType.ANILLOS,
            ItemType.POTION: ObjType.POCIONES,
            ItemType.FOOD: ObjType.COMIDA,
            ItemType.MISC: ObjType.COMIDA,  # Uso genérico si no existe un ObjType de catálogo.
        }
        return type_map.get(self, 1)


@dataclass
class Item:
    """Representa un item del juego."""

    item_id: int
    name: str
    item_type: ItemType
    graphic_id: int  # ID del gráfico para mostrar en cliente
    stackable: bool = False
    max_stack: int = 1
    consumable: bool = False
    equippable: bool = False
    value: int = 0  # Valor en oro
    obj_type: int = 0  # Tipo original para especialidades de los comerciantes.

    # Efectos al usar (para pociones/comida)
    restore_hp: int = 0
    restore_mana: int = 0
    restore_stamina: int = 0
    restore_hunger: int = 0
    restore_thirst: int = 0

    # Stats para equipamiento
    min_damage: int = 0
    max_damage: int = 0
    defense: int = 0
    max_defense: int | None = None
    animation: int = 0
    body_animation: int = 0
    dwarf_animation: int = 0

    def to_client_type(self) -> int:
        """Conserva el ObjType real sin colapsar barcos, pergaminos o equipo en MISC.

        Returns:
            Tipo canónico del protocolo AO, o el tipo básico para objetos construidos a mano.
        """
        return self.obj_type or self.item_type.to_client_type()

    def __post_init__(self) -> None:
        """Validaciones después de inicialización."""
        if self.stackable and self.max_stack < 1:
            self.max_stack = 99  # Default para stackables
        if self.max_defense is None:
            self.max_defense = self.defense

    def can_use(self) -> bool:
        """Verifica si el item se puede usar.

        Returns:
            True si el item es consumible o equipable.
        """
        return self.consumable or self.equippable

    def get_total_restore(self) -> int:
        """Calcula el total de restauración del item.

        Returns:
            Suma de todos los valores de restauración.
        """
        return (
            self.restore_hp
            + self.restore_mana
            + self.restore_stamina
            + self.restore_hunger
            + self.restore_thirst
        )
