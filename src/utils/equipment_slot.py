"""Definición de slots de equipamiento."""

from enum import Enum


class EquipmentSlot(Enum):
    """Slots de equipamiento disponibles."""

    BOOTS = "boots"
    WEAPON = "weapon"  # Arma
    ARMOR = "armor"  # Armadura
    HELMET = "helmet"  # Casco
    SHIELD = "shield"  # Escudo
    ACCESSORY = "accessory"  # Un anillo o foco musical; no tiene capa de avatar.

    @classmethod
    def from_item_type(cls, item_type: str) -> EquipmentSlot | None:
        """Obtiene el slot de equipamiento según el tipo de item.

        Args:
            item_type: Tipo de item (weapon, armor, helmet, shield).

        Returns:
            Slot de equipamiento correspondiente o None si no es equipable.
        """
        mapping = {
            "boots": cls.BOOTS,
            "weapon": cls.WEAPON,
            "armor": cls.ARMOR,
            "helmet": cls.HELMET,
            "shield": cls.SHIELD,
            "accessory": cls.ACCESSORY,
        }
        return mapping.get(item_type)
