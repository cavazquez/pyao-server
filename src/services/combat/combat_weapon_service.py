"""Servicio para obtener stats de armas y armaduras."""

import logging
import random
from typing import TYPE_CHECKING

from src.constants.gameplay import BASE_ARMOR_REDUCTION, BASE_FIST_DAMAGE
from src.utils.equipment_slot import EquipmentSlot

if TYPE_CHECKING:
    from src.models.item_catalog import ItemCatalog
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.inventory_repository import InventoryRepository

logger = logging.getLogger(__name__)


class WeaponService:
    """Obtiene información de armas y armaduras equipadas.

    Esta clase encapsula la lógica de obtener stats de equipamiento
    desde los repositorios y el catálogo de items.
    """

    def __init__(
        self,
        equipment_repo: EquipmentRepository,
        inventory_repo: InventoryRepository,
        item_catalog: ItemCatalog | None = None,
    ) -> None:
        """Inicializa el servicio de armas.

        Args:
            equipment_repo: Repositorio de equipamiento.
            inventory_repo: Repositorio de inventario.
            item_catalog: Catálogo de items para obtener stats de armas/armaduras.
        """
        self.equipment_repo = equipment_repo
        self.inventory_repo = inventory_repo
        self.item_catalog = item_catalog

    async def get_weapon_damage(self, user_id: int) -> int:
        """Obtiene el daño del arma equipada.

        El daño se calcula como un valor aleatorio entre MinHit y MaxHit
        del arma equipada, según los datos del catálogo de items.

        Args:
            user_id: ID del jugador.

        Returns:
            Daño del arma (BASE_FIST_DAMAGE si no tiene arma = puños).
        """
        # Obtener equipamiento
        equipment = await self.equipment_repo.get_all_equipment(user_id)
        weapon_inventory_slot = equipment.get(EquipmentSlot.WEAPON)

        if not weapon_inventory_slot:
            return BASE_FIST_DAMAGE  # Daño base sin arma (puños)

        # Obtener item del inventario
        slot_data = await self.inventory_repo.get_slot(user_id, weapon_inventory_slot)
        if not slot_data:
            return BASE_FIST_DAMAGE

        item_id, _quantity = slot_data

        # Obtener daño desde ItemCatalog
        if self.item_catalog:
            damage_range = self.item_catalog.get_weapon_damage(item_id)
            if damage_range:
                min_hit, max_hit = damage_range
                return random.randint(min_hit, max_hit)

        # Fallback: daño base si no hay catálogo o el item no es arma
        return BASE_FIST_DAMAGE

    async def get_armor_reduction(self, user_id: int) -> float:
        """Obtiene la reducción de daño por armadura.

        Calcula la reducción basándose en la armadura equipada.
        El porcentaje se basa en la defensa promedio de la armadura.

        Args:
            user_id: ID del jugador.

        Returns:
            Porcentaje de reducción (0.0 - 1.0).
        """
        # Obtener equipamiento
        equipment = await self.equipment_repo.get_all_equipment(user_id)
        armor_inventory_slot = equipment.get(EquipmentSlot.ARMOR)

        if not armor_inventory_slot:
            return BASE_ARMOR_REDUCTION

        # Obtener item del inventario
        slot_data = await self.inventory_repo.get_slot(user_id, armor_inventory_slot)
        if not slot_data:
            return BASE_ARMOR_REDUCTION

        item_id, _quantity = slot_data

        # Obtener defensa desde ItemCatalog
        if self.item_catalog:
            defense_range = self.item_catalog.get_armor_defense(item_id)
            if defense_range:
                min_def, max_def = defense_range
                avg_defense = (min_def + max_def) / 2
                # Escalar la reducción: 10 de defensa = 10% reducción adicional
                # Cap máximo de 50% reducción
                reduction = BASE_ARMOR_REDUCTION + (avg_defense / 100)
                return min(reduction, 0.5)

        return BASE_ARMOR_REDUCTION
