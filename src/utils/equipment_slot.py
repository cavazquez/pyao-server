"""Definición de slots de equipamiento."""

from enum import Enum


class EquipmentSlot(Enum):
    """Slots de equipamiento disponibles."""

    WEAPON = "weapon"  # Arma
    ARMOR = "armor"  # Armadura
    HELMET = "helmet"  # Casco
    SHIELD = "shield"  # Escudo

    @classmethod
    def from_item_type(cls, item_type: str) -> EquipmentSlot | None:
        """Obtiene el slot de equipamiento según el tipo de item.

        Args:
            item_type: Tipo de item (weapon, armor, helmet, shield).

        Returns:
            Slot de equipamiento correspondiente o None si no es equipable.
        """
        mapping = {
            "weapon": cls.WEAPON,
            "armor": cls.ARMOR,
            "helmet": cls.HELMET,
            "shield": cls.SHIELD,
        }
        return mapping.get(item_type)
