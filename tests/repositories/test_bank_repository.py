"""Tests para el repositorio de banco."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from src.repositories.bank_repository import BankRepository

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


@pytest.mark.asyncio
class TestBankRepository:
    """Tests para BankRepository."""

    async def test_initialize_empty_bank(self, redis_client: RedisClient) -> None:
        """Test de inicialización de bóveda vacía."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Obtener banco (debe inicializarse automáticamente)
        bank = await repo.get_bank(user_id)

        # Verificar que tiene 40 slots vacíos (según configuración)
        assert len(bank) == 40
        for i in range(1, 41):
            slot_key = f"slot_{i}"
            assert slot_key in bank
            assert not bank[slot_key]

    async def test_deposit_item_new_slot(self, redis_client: RedisClient) -> None:
        """Test de depósito de item en slot vacío."""
        repo = BankRepository(redis_client)
        user_id = 1
        item_id = 10
        quantity = 5

        # Depositar item
        slot = await repo.deposit_item(user_id, item_id, quantity)

        # Verificar que se depositó en un slot
        assert slot is not None
        assert 1 <= slot <= 20

        # Verificar que el item está en el banco
        bank_item = await repo.get_item(user_id, slot)
        assert bank_item is not None
        assert bank_item.item_id == item_id
        assert bank_item.quantity == quantity
        assert bank_item.slot == slot

    async def test_deposit_item_stack(self, redis_client: RedisClient) -> None:
        """Test de apilamiento de items del mismo tipo."""
        repo = BankRepository(redis_client)
        user_id = 1
        item_id = 10

        # Depositar primera vez
        slot1 = await repo.deposit_item(user_id, item_id, 5)
        assert slot1 is not None

        # Depositar segunda vez (debe apilar)
        slot2 = await repo.deposit_item(user_id, item_id, 3)
        assert slot2 == slot1  # Mismo slot

        # Verificar cantidad total
        bank_item = await repo.get_item(user_id, slot1)
        assert bank_item is not None
        assert bank_item.quantity == 8

    async def test_deposit_item_full_bank(self, redis_client: RedisClient) -> None:
        """Test de depósito cuando el banco está lleno."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Llenar todos los slots con items diferentes
        for i in range(1, 41):
            slot = await repo.deposit_item(user_id, item_id=i, quantity=1)
            assert slot == i

        # Intentar depositar otro item diferente (no debe haber espacio)
        slot = await repo.deposit_item(user_id, item_id=99, quantity=1)
        assert slot is None

    async def test_extract_item_success(self, redis_client: RedisClient) -> None:
        """Test de extracción exitosa de item."""
        repo = BankRepository(redis_client)
        user_id = 1
        item_id = 10
        quantity = 10

        # Depositar item
        slot = await repo.deposit_item(user_id, item_id, quantity)
        assert slot is not None

        # Extraer parte del item
        success = await repo.extract_item(user_id, slot, 3)
        assert success is True

        # Verificar cantidad restante
        bank_item = await repo.get_item(user_id, slot)
        assert bank_item is not None
        assert bank_item.quantity == 7

    async def test_extract_item_all(self, redis_client: RedisClient) -> None:
        """Test de extracción completa de item (vacía el slot)."""
        repo = BankRepository(redis_client)
        user_id = 1
        item_id = 10
        quantity = 5

        # Depositar item
        slot = await repo.deposit_item(user_id, item_id, quantity)
        assert slot is not None

        # Extraer todo
        success = await repo.extract_item(user_id, slot, quantity)
        assert success is True

        # Verificar que el slot está vacío
        bank_item = await repo.get_item(user_id, slot)
        assert bank_item is None

    async def test_extract_item_insufficient_quantity(self, redis_client: RedisClient) -> None:
        """Test de extracción con cantidad insuficiente."""
        repo = BankRepository(redis_client)
        user_id = 1
        item_id = 10

        # Depositar item
        slot = await repo.deposit_item(user_id, item_id, 5)
        assert slot is not None

        # Intentar extraer más de lo que hay
        success = await repo.extract_item(user_id, slot, 10)
        assert success is False

        # Verificar que no cambió la cantidad
        bank_item = await repo.get_item(user_id, slot)
        assert bank_item is not None
        assert bank_item.quantity == 5

    async def test_extract_item_empty_slot(self, redis_client: RedisClient) -> None:
        """Test de extracción de slot vacío."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Intentar extraer de slot vacío
        success = await repo.extract_item(user_id, slot=1, quantity=1)
        assert success is False

    async def test_extract_item_invalid_slot(self, redis_client: RedisClient) -> None:
        """Test de extracción con slot inválido."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Slot fuera de rango
        success = await repo.extract_item(user_id, slot=0, quantity=1)
        assert success is False

        success = await repo.extract_item(user_id, slot=41, quantity=1)
        assert success is False

    async def test_get_all_items(self, redis_client: RedisClient) -> None:
        """Test de obtención de todos los items."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Depositar varios items
        await repo.deposit_item(user_id, item_id=1, quantity=5)
        await repo.deposit_item(user_id, item_id=2, quantity=10)
        await repo.deposit_item(user_id, item_id=3, quantity=3)

        # Obtener todos los items
        items = await repo.get_all_items(user_id)

        # Verificar que hay 3 items
        assert len(items) == 3

        # Verificar que todos tienen datos correctos
        item_ids = {item.item_id for item in items}
        assert item_ids == {1, 2, 3}

    async def test_get_item_invalid_slot(self, redis_client: RedisClient) -> None:
        """Test de obtención de item con slot inválido."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Slot fuera de rango
        item = await repo.get_item(user_id, slot=0)
        assert item is None

        item = await repo.get_item(user_id, slot=41)
        assert item is None

    async def test_multiple_users_isolation(self, redis_client: RedisClient) -> None:
        """Test de aislamiento entre bóvedas de diferentes usuarios."""
        repo = BankRepository(redis_client)
        user1 = 1
        user2 = 2
        item_id = 10

        # Usuario 1 deposita
        slot1 = await repo.deposit_item(user1, item_id, 5)
        assert slot1 is not None

        # Usuario 2 deposita
        slot2 = await repo.deposit_item(user2, item_id, 3)
        assert slot2 is not None

        # Verificar que cada usuario tiene su propio item
        item1 = await repo.get_item(user1, slot1)
        item2 = await repo.get_item(user2, slot2)

        assert item1 is not None
        assert item1.quantity == 5

        assert item2 is not None
        assert item2.quantity == 3

        # Verificar que no se mezclan
        items1 = await repo.get_all_items(user1)
        items2 = await repo.get_all_items(user2)

        assert len(items1) == 1
        assert len(items2) == 1

    async def test_deposit_zero_quantity(self, redis_client: RedisClient) -> None:
        """Test de depósito con cantidad cero o negativa."""
        repo = BankRepository(redis_client)
        user_id = 1

        # Depositar cantidad cero (debería funcionar pero no es útil)
        await repo.deposit_item(user_id, item_id=1, quantity=0)
        # El comportamiento depende de la implementación
        # pero no debería crashear

    async def test_bank_persistence(self, redis_client: RedisClient) -> None:
        """Test de persistencia de datos en Redis."""
        repo = BankRepository(redis_client)
        user_id = 1
        item_id = 10
        quantity = 5

        # Depositar item
        slot = await repo.deposit_item(user_id, item_id, quantity)
        assert slot is not None

        # Crear nueva instancia del repositorio (simula reconexión)
        repo2 = BankRepository(redis_client)

        # Verificar que el item sigue ahí
        bank_item = await repo2.get_item(user_id, slot)
        assert bank_item is not None
        assert bank_item.item_id == item_id
        assert bank_item.quantity == quantity
