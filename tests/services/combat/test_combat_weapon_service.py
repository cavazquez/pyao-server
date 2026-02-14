"""Tests para WeaponService."""

import math
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.constants.gameplay import BASE_ARMOR_REDUCTION, BASE_FIST_DAMAGE
from src.services.combat.combat_weapon_service import WeaponService
from src.utils.equipment_slot import EquipmentSlot


@pytest.fixture
def equipment_repo() -> MagicMock:
    """Fixture para mock de EquipmentRepository."""
    return MagicMock()


@pytest.fixture
def inventory_repo() -> MagicMock:
    """Fixture para mock de InventoryRepository."""
    return MagicMock()


@pytest.fixture
def item_catalog() -> MagicMock:
    """Fixture para mock de ItemCatalog."""
    catalog = MagicMock()
    # Configurar respuestas por defecto
    catalog.get_weapon_damage.return_value = None
    catalog.get_armor_defense.return_value = None
    return catalog


@pytest.mark.asyncio
class TestWeaponService:
    """Tests para WeaponService."""

    async def test_init(self, equipment_repo: MagicMock, inventory_repo: MagicMock) -> None:
        """Test de inicialización."""
        service = WeaponService(equipment_repo, inventory_repo)

        assert service.equipment_repo == equipment_repo
        assert service.inventory_repo == inventory_repo
        assert service.item_catalog is None

    async def test_init_with_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de inicialización con catálogo."""
        service = WeaponService(equipment_repo, inventory_repo, item_catalog)

        assert service.item_catalog == item_catalog

    async def test_get_weapon_damage_no_weapon(
        self, equipment_repo: MagicMock, inventory_repo: MagicMock
    ) -> None:
        """Test de daño sin arma equipada (puños)."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={})

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == BASE_FIST_DAMAGE  # Daño de puños

    async def test_get_weapon_damage_with_sword_from_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de daño con espada equipada usando catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 5})
        inventory_repo.get_slot = AsyncMock(return_value=(2, 1))  # Espada Larga

        # Espada Larga: MinHit=1, MaxHit=8
        item_catalog.get_weapon_damage.return_value = (1, 8)

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        damage = await service.get_weapon_damage(1)

        # El daño debe estar entre min y max
        assert 1 <= damage <= 8
        item_catalog.get_weapon_damage.assert_called_once_with(2)

    async def test_get_weapon_damage_with_axe_from_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de daño con hacha equipada usando catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 3})
        inventory_repo.get_slot = AsyncMock(return_value=(3, 1))  # Hacha

        # Hacha: MinHit=2, MaxHit=6
        item_catalog.get_weapon_damage.return_value = (2, 6)

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        damage = await service.get_weapon_damage(1)

        assert 2 <= damage <= 6
        item_catalog.get_weapon_damage.assert_called_once_with(3)

    async def test_get_weapon_damage_unknown_weapon_no_catalog(
        self, equipment_repo: MagicMock, inventory_repo: MagicMock
    ) -> None:
        """Test de daño con arma desconocida sin catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(999, 1))  # ID desconocido

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == BASE_FIST_DAMAGE  # Fallback sin catálogo

    async def test_get_weapon_damage_unknown_weapon_with_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de daño con arma desconocida en catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(999, 1))  # ID desconocido

        # El catálogo no conoce el item
        item_catalog.get_weapon_damage.return_value = None

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        damage = await service.get_weapon_damage(1)

        assert damage == BASE_FIST_DAMAGE  # Fallback

    async def test_get_weapon_damage_slot_empty(
        self, equipment_repo: MagicMock, inventory_repo: MagicMock
    ) -> None:
        """Test cuando el slot de arma está vacío."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 5})
        inventory_repo.get_slot = AsyncMock(return_value=None)

        service = WeaponService(equipment_repo, inventory_repo)
        damage = await service.get_weapon_damage(1)

        assert damage == BASE_FIST_DAMAGE  # Daño de puños

    async def test_get_weapon_damage_dagger_from_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de daño con daga desde catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 2})
        inventory_repo.get_slot = AsyncMock(return_value=(15, 1))  # Daga ID=15

        # Daga: MinHit=1, MaxHit=2
        item_catalog.get_weapon_damage.return_value = (1, 2)

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        damage = await service.get_weapon_damage(1)

        assert 1 <= damage <= 2

    async def test_get_weapon_damage_two_handed_sword_from_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de daño con espada de dos manos desde catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(19, 1))  # Espada 2H ID=19

        # Espada 2H: MinHit=4, MaxHit=9
        item_catalog.get_weapon_damage.return_value = (4, 9)

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        damage = await service.get_weapon_damage(1)

        assert 4 <= damage <= 9

    async def test_get_armor_reduction_default(
        self, equipment_repo: MagicMock, inventory_repo: MagicMock
    ) -> None:
        """Test de reducción de armadura por defecto."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={})

        service = WeaponService(equipment_repo, inventory_repo)
        reduction = await service.get_armor_reduction(1)

        assert reduction == BASE_ARMOR_REDUCTION  # 10% de reducción base

    async def test_get_armor_reduction_no_armor_slot(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de reducción sin armadura equipada."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={})

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        reduction = await service.get_armor_reduction(1)

        assert reduction == BASE_ARMOR_REDUCTION

    async def test_get_armor_reduction_with_armor_from_catalog(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de reducción con armadura desde catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.ARMOR: 3})
        inventory_repo.get_slot = AsyncMock(return_value=(100, 1))  # Armadura ID=100

        # Armadura con defensa 10-20 → promedio 15
        item_catalog.get_armor_defense.return_value = (10, 20)

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        reduction = await service.get_armor_reduction(1)

        # 0.1 base + 15/100 = 0.25
        assert reduction == pytest.approx(0.25, rel=0.01)

    async def test_get_armor_reduction_max_cap(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test que la reducción de armadura tiene cap de 50%."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.ARMOR: 3})
        inventory_repo.get_slot = AsyncMock(return_value=(200, 1))  # Armadura épica

        # Armadura con defensa muy alta → 50-60 promedio 55
        item_catalog.get_armor_defense.return_value = (50, 60)

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        reduction = await service.get_armor_reduction(1)

        # Sin cap sería 0.1 + 55/100 = 0.65, pero con cap = 0.5
        assert math.isclose(reduction, 0.5)

    async def test_get_armor_reduction_unknown_armor(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test de reducción con armadura desconocida en catálogo."""
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.ARMOR: 3})
        inventory_repo.get_slot = AsyncMock(return_value=(999, 1))  # ID desconocido

        # El catálogo no conoce el item
        item_catalog.get_armor_defense.return_value = None

        service = WeaponService(equipment_repo, inventory_repo, item_catalog)
        reduction = await service.get_armor_reduction(1)

        assert reduction == BASE_ARMOR_REDUCTION

    async def test_multiple_users(
        self,
        equipment_repo: MagicMock,
        inventory_repo: MagicMock,
        item_catalog: MagicMock,
    ) -> None:
        """Test con múltiples usuarios."""
        service = WeaponService(equipment_repo, inventory_repo, item_catalog)

        # Usuario 1 con espada
        equipment_repo.get_all_equipment = AsyncMock(return_value={EquipmentSlot.WEAPON: 1})
        inventory_repo.get_slot = AsyncMock(return_value=(2, 1))
        item_catalog.get_weapon_damage.return_value = (5, 10)

        damage1 = await service.get_weapon_damage(1)
        assert 5 <= damage1 <= 10

        # Usuario 2 sin arma
        equipment_repo.get_all_equipment = AsyncMock(return_value={})
        damage2 = await service.get_weapon_damage(2)

        assert damage2 == BASE_FIST_DAMAGE
