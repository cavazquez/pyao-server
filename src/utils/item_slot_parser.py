"""Utilidad para parsear items en formato item_id:quantity desde Redis."""

import logging
from dataclasses import dataclass

from src.utils.inventory_slot import InventorySlot

logger = logging.getLogger(__name__)


@dataclass
class ParsedItem:
    """Representa un item parseado desde Redis."""

    item_id: int
    quantity: int
    instance_ids: tuple[str, ...] = ()

    def to_string(self) -> str:
        """Convierte el item a formato Redis (item_id:quantity).

        Returns:
            String en formato "item_id:quantity".
        """
        return InventorySlot(self.item_id, self.quantity, self.instance_ids).to_string()


class ItemSlotParser:
    """Parser para items almacenados en Redis en formato item_id:quantity."""

    @staticmethod
    def parse(value: str | bytes | None) -> ParsedItem | None:
        """Parsea un valor de Redis en formato item_id:quantity.

        Args:
            value: Valor de Redis (string, bytes o None).

        Returns:
            ParsedItem con item_id y quantity, o None si el parsing falla.
        """
        if not value:
            return None

        try:
            # Convertir bytes a string si es necesario
            if isinstance(value, bytes):
                value = value.decode("utf-8")

            # Parsear formato "item_id:quantity"
            parsed = InventorySlot.parse(value)
            return (
                ParsedItem(parsed.item_id, parsed.quantity, parsed.instance_ids) if parsed else None
            )
        except (ValueError, AttributeError) as e:
            logger.debug("Error parseando item slot: %s - %s", value, e)
            return None

    @staticmethod
    def parse_slot_number(slot_key: str) -> int | None:
        """Extrae el número de slot de una key en formato slot_N.

        Args:
            slot_key: Key en formato "slot_1", "slot_2", etc.

        Returns:
            Número de slot o None si el parsing falla.
        """
        try:
            return int(str(slot_key).split("_")[1])
        except IndexError, ValueError:
            logger.debug("Error parseando número de slot: %s", slot_key)
            return None

    @staticmethod
    def format_value(item_id: int, quantity: int) -> str:
        """Formatea un item para almacenar en Redis.

        Args:
            item_id: ID del item.
            quantity: Cantidad del item.

        Returns:
            String en formato "item_id:quantity".
        """
        return f"{item_id}:{quantity}"
