"""Tests para WeaponService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.services.combat.combat_weapon_service import WeaponService
from src.utils.equipment_slot import EquipmentSlot


@pytest.mark.asyncio
class TestWeaponService:
    """Tests para WeaponService."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        service = WeaponService(equipment_repo, inventory_repo)

        assert service.equipment_repo == equipment_repo
        assert service.inventory_repo == inventory_repo
        assert isinstance(service.weapon_damages, dict)

    async def test_get_weapon_damage_no_weapon(self) -> None:
        """Test de daño sin arma equipada (puños)."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={})

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 2  # Daño de puños

    async def test_get_weapon_damage_with_sword(self) -> None:
        """Test de daño con espada equipada."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 5})
        inventory_repo.get_slot = AsyncMock(return_value=(2, 1))  # Espada Larga

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 15  # Daño de Espada Larga

    async def test_get_weapon_damage_with_axe(self) -> None:
        """Test de daño con hacha equipada."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 3})
        inventory_repo.get_slot = AsyncMock(return_value=(3, 1))  # Hacha

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 12  # Daño de Hacha

    async def test_get_weapon_damage_unknown_weapon(self) -> None:
        """Test de daño con arma desconocida."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(999, 1))  # ID desconocido

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 5  # Daño por defecto

    async def test_get_weapon_damage_slot_empty(self) -> None:
        """Test cuando el slot de arma está vacío."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 5})
        inventory_repo.get_slot = AsyncMock(return_value=None)

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 2  # Daño de puños

    async def test_get_weapon_damage_dagger(self) -> None:
        """Test de daño con daga."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 2})
        inventory_repo.get_slot = AsyncMock(return_value=(4, 1))  # Daga

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 10  # Daño de Daga

    async def test_get_weapon_damage_two_handed_sword(self) -> None:
        """Test de daño con espada de dos manos."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(5, 1))  # Espada 2H

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == 20  # Daño de Espada de Dos Manos

    async def test_get_armor_reduction_default(self) -> None:
        """Test de reducción de armadura por defecto."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        service = WeaponService(equipment_repo, inventory_repo)
        reduction = await service.get_armor_reduction(1)

        assert reduction == 0.1  # 10% de reducción base

    async def test_weapon_damages_table(self) -> None:
        """Test que la tabla de daños tiene las armas esperadas."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        service = WeaponService(equipment_repo, inventory_repo)

        assert 2 in service.weapon_damages  # Espada Larga
        assert 3 in service.weapon_damages  # Hacha
        assert 4 in service.weapon_damages  # Daga
        assert 5 in service.weapon_damages  # Espada 2H

    async def test_multiple_users(self) -> None:
        """Test con múltiples usuarios."""
        equipment_repo = MagicMock()
        inventory_repo = MagicMock()

        # Usuario 1 con espada
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(2, 1))

        service = WeaponService(equipment_repo, inventory_repo)
        damage1 = await service.get_weapon_damage(1)

        # Usuario 2 sin arma
        equipment_repo.get_all_equipment = AsyncMock(return_value={})
        damage2 = await service.get_weapon_damage(2)

        assert damage1 == 15
        assert damage2 == 2
