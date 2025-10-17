"""Tests para EquipmentRepository."""

# ruff: noqa: DOC402

from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from src.equipment_repository import EquipmentRepository
from src.equipment_slot import EquipmentSlot

if TYPE_CHECKING:
    from src.redis_client import RedisClient


@pytest_asyncio.fixture
async def equipment_repo(redis_client: RedisClient) -> EquipmentRepository:
    """Crea un repositorio de equipamiento para tests.

    Usa el fixture redis_client de conftest.py que ya tiene fakeredis configurado.
    """
    return EquipmentRepository(redis_client)


@pytest_asyncio.fixture(autouse=True)
async def cleanup_redis(redis_client: RedisClient) -> None:
    """Limpia Redis antes y después de cada test."""
    if redis_client.redis:
        await redis_client.redis.flushdb()
    yield
    if redis_client.redis:
        await redis_client.redis.flushdb()


class TestEquipmentRepository:
    """Tests para EquipmentRepository."""

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_equip_item(self, equipment_repo: EquipmentRepository) -> None:
        """Test equipar un item."""
        user_id = 1
        slot = EquipmentSlot.WEAPON
        inventory_slot = 5

        result = await equipment_repo.equip_item(user_id, slot, inventory_slot)

        assert result is True

        # Verificar que se guardó correctamente
        equipped_slot = await equipment_repo.get_equipped_slot(user_id, slot)
        assert equipped_slot == inventory_slot

    @pytest.mark.asyncio
    async def test_unequip_item(self, equipment_repo: EquipmentRepository) -> None:
        """Test desequipar un item."""
        user_id = 1
        slot = EquipmentSlot.WEAPON
        inventory_slot = 5

        # Equipar primero
        await equipment_repo.equip_item(user_id, slot, inventory_slot)

        # Desequipar
        result = await equipment_repo.unequip_item(user_id, slot)
        assert result is True

        # Verificar que se eliminó
        equipped_slot = await equipment_repo.get_equipped_slot(user_id, slot)
        assert equipped_slot is None

    @pytest.mark.asyncio
    async def test_unequip_empty_slot(self, equipment_repo: EquipmentRepository) -> None:
        """Test desequipar un slot vacío."""
        user_id = 1
        slot = EquipmentSlot.WEAPON

        result = await equipment_repo.unequip_item(user_id, slot)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_equipped_slot(self, equipment_repo: EquipmentRepository) -> None:
        """Test obtener item equipado en un slot."""
        user_id = 1
        slot = EquipmentSlot.ARMOR
        inventory_slot = 3

        # Slot vacío
        result = await equipment_repo.get_equipped_slot(user_id, slot)
        assert result is None

        # Equipar y verificar
        await equipment_repo.equip_item(user_id, slot, inventory_slot)
        result = await equipment_repo.get_equipped_slot(user_id, slot)
        assert result == inventory_slot

    @pytest.mark.asyncio
    async def test_get_all_equipment(self, equipment_repo: EquipmentRepository) -> None:
        """Test obtener todo el equipamiento."""
        user_id = 1

        # Sin equipamiento
        equipment = await equipment_repo.get_all_equipment(user_id)
        assert equipment == {}

        # Equipar varios items
        await equipment_repo.equip_item(user_id, EquipmentSlot.WEAPON, 5)
        await equipment_repo.equip_item(user_id, EquipmentSlot.ARMOR, 3)
        await equipment_repo.equip_item(user_id, EquipmentSlot.HELMET, 2)

        equipment = await equipment_repo.get_all_equipment(user_id)
        assert equipment == {
            EquipmentSlot.WEAPON: 5,
            EquipmentSlot.ARMOR: 3,
            EquipmentSlot.HELMET: 2,
        }

    @pytest.mark.asyncio
    async def test_is_slot_equipped(self, equipment_repo: EquipmentRepository) -> None:
        """Test verificar si un slot del inventario está equipado."""
        user_id = 1
        inventory_slot = 5

        # No equipado
        result = await equipment_repo.is_slot_equipped(user_id, inventory_slot)
        assert result is None

        # Equipar
        await equipment_repo.equip_item(user_id, EquipmentSlot.WEAPON, inventory_slot)

        # Verificar que está equipado
        result = await equipment_repo.is_slot_equipped(user_id, inventory_slot)
        assert result == EquipmentSlot.WEAPON

    @pytest.mark.asyncio
    async def test_clear_equipment(self, equipment_repo: EquipmentRepository) -> None:
        """Test limpiar todo el equipamiento."""
        user_id = 1

        # Equipar varios items
        await equipment_repo.equip_item(user_id, EquipmentSlot.WEAPON, 5)
        await equipment_repo.equip_item(user_id, EquipmentSlot.ARMOR, 3)

        # Limpiar
        result = await equipment_repo.clear_equipment(user_id)
        assert result is True

        # Verificar que se limpió
        equipment = await equipment_repo.get_all_equipment(user_id)
        assert equipment == {}

    @pytest.mark.asyncio
    async def test_replace_equipped_item(self, equipment_repo: EquipmentRepository) -> None:
        """Test reemplazar un item equipado."""
        user_id = 1
        slot = EquipmentSlot.WEAPON

        # Equipar primer item
        await equipment_repo.equip_item(user_id, slot, 5)

        # Equipar segundo item en el mismo slot (reemplaza)
        await equipment_repo.equip_item(user_id, slot, 7)

        # Verificar que se reemplazó
        equipped_slot = await equipment_repo.get_equipped_slot(user_id, slot)
        assert equipped_slot == 7

    @pytest.mark.asyncio
    async def test_multiple_users(self, equipment_repo: EquipmentRepository) -> None:
        """Test equipamiento de múltiples usuarios."""
        user1 = 1
        user2 = 2

        # Equipar items para ambos usuarios
        await equipment_repo.equip_item(user1, EquipmentSlot.WEAPON, 5)
        await equipment_repo.equip_item(user2, EquipmentSlot.WEAPON, 3)

        # Verificar que cada usuario tiene su propio equipamiento
        equipment1 = await equipment_repo.get_all_equipment(user1)
        equipment2 = await equipment_repo.get_all_equipment(user2)

        assert equipment1 == {EquipmentSlot.WEAPON: 5}
        assert equipment2 == {EquipmentSlot.WEAPON: 3}
