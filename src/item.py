"""Modelo de datos para items del juego."""

from dataclasses import dataclass
from enum import Enum


class ItemType(Enum):
    """Tipos de items."""

    WEAPON = "weapon"
    ARMOR = "armor"
    HELMET = "helmet"
    SHIELD = "shield"
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
            ItemType.WEAPON: 2,  # otWeapon
            ItemType.ARMOR: 3,  # otArmadura
            ItemType.HELMET: 4,  # otCASCO
            ItemType.SHIELD: 5,  # otESCUDO
            ItemType.POTION: 6,  # otPociones
            ItemType.FOOD: 7,  # otBebidas
            ItemType.MISC: 1,  # otUseOnce o genérico
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

    def __post_init__(self) -> None:
        """Validaciones después de inicialización."""
        if self.stackable and self.max_stack < 1:
            self.max_stack = 99  # Default para stackables

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
