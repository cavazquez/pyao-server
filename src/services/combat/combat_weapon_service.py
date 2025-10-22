"""Servicio para obtener stats de armas y armaduras."""

import logging
from typing import TYPE_CHECKING

from src.utils.equipment_slot import EquipmentSlot

if TYPE_CHECKING:
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.inventory_repository import InventoryRepository

logger = logging.getLogger(__name__)


class WeaponService:
    """Obtiene información de armas y armaduras equipadas.

    Esta clase encapsula la lógica de obtener stats de equipamiento
    desde los repositorios.
    """

    def __init__(
        self,
        equipment_repo: EquipmentRepository,
        inventory_repo: InventoryRepository,
    ) -> None:
        """Inicializa el servicio de armas.

        Args:
            equipment_repo: Repositorio de equipamiento.
            inventory_repo: Repositorio de inventario.
        """
        self.equipment_repo = equipment_repo
        self.inventory_repo = inventory_repo

        # Tabla temporal de daño de armas
        # TODO: Mover a ItemCatalog
        self.weapon_damages = {
            2: 15,  # Espada Larga
            3: 12,  # Hacha
            4: 10,  # Daga
            5: 20,  # Espada de Dos Manos
        }

    async def get_weapon_damage(self, user_id: int) -> int:
        """Obtiene el daño del arma equipada.

        Args:
            user_id: ID del jugador.

        Returns:
            Daño del arma (2 si no tiene arma = puños).
        """
        # Obtener equipamiento
        equipment = await self.equipment_repo.get_all_equipment(user_id)
        weapon_inventory_slot = equipment.get(EquipmentSlot.WEAPON)

        if not weapon_inventory_slot:
            return 2  # Daño base sin arma (puños)

        # Obtener item del inventario
        slot_data = await self.inventory_repo.get_slot(user_id, weapon_inventory_slot)
        if not slot_data:
            return 2

        item_id, _quantity = slot_data
        return self.weapon_damages.get(item_id, 5)

    @staticmethod
    async def get_armor_reduction(_user_id: int) -> float:
        """Obtiene la reducción de daño por armadura.

        Args:
            _user_id: ID del jugador (no usado aún, para futura implementación).

        Returns:
            Porcentaje de reducción (0.0 - 1.0).
        """
        # TODO: Implementar cuando tengamos armaduras
        # Por ahora retorna reducción base
        return 0.1  # 10% de reducción base
