"""Apariencia única del equipo, muerte, mimetismo y navegación."""

import time
from collections.abc import Mapping
from dataclasses import dataclass

from src.models.items_catalog import ITEMS_CATALOG
from src.utils.inventory_slot import InventorySlot

GHOST_BODY = 500
GHOST_HEAD = 500
SMALL_RACES = frozenset({4, 5})


@dataclass(frozen=True, slots=True)
class PlayerAppearance:
    """Gráficos del personaje; cero retira explícitamente una pieza."""

    body: int
    head: int
    weapon: int = 0
    shield: int = 0
    helmet: int = 0
    boots: int = 0

    def equipment(self) -> dict[str, int]:
        """Obtiene las capas opcionales para los paquetes de personaje.

        Returns:
            Animaciones completas, incluso las piezas retiradas.
        """
        return {
            "weapon": self.weapon,
            "shield": self.shield,
            "helmet": self.helmet,
            "boots": self.boots,
        }


def resolve_appearance(
    account: Mapping[str, str],
    stats: Mapping[str, str],
    equipment: Mapping[str, str],
    inventory: Mapping[str, str],
) -> PlayerAppearance:
    """Resuelve el catálogo propio sin confundir GrhIndex con animaciones equipadas.

    Returns:
        Apariencia efectiva; los estados que reemplazan al cuerpo ocultan el equipo.
    """
    body = int(account.get("char_body", account.get("char_race", 1))) or 1
    head = int(account.get("char_head", 1))
    if int(stats.get("min_hp", stats.get("hp", 1))) <= 0:
        return PlayerAppearance(GHOST_BODY, GHOST_HEAD)
    if stats.get("sailing") == "1":
        return PlayerAppearance(84, 0)
    if float(stats.get("morphed_until", 0)) > time.time():
        return PlayerAppearance(
            int(stats.get("morphed_body", body)), int(stats.get("morphed_head", head))
        )
    layers = {"weapon": 0, "shield": 0, "helmet": 0, "boots": 0}
    for slot in ("armor", *layers):
        stack = InventorySlot.parse(inventory.get(f"slot_{equipment.get(slot, '0')}", ""))
        item = ITEMS_CATALOG.get(stack.item_id) if stack else None
        if item is None or item.item_type.value != slot:
            continue
        if slot == "armor":
            body = item.body_animation or body
        else:
            animation = item.animation
            if slot == "weapon" and int(account.get("char_race", 1)) in SMALL_RACES:
                animation = item.dwarf_animation or animation
            layers[slot] = animation
    return PlayerAppearance(body, head, **layers)
