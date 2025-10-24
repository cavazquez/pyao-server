"""Tests para SpellbookRepository."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest

from src.repositories.spellbook_repository import SpellbookRepository

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


@pytest.mark.asyncio
class TestSpellbookRepository:
    """Tests para SpellbookRepository."""

    async def test_add_spell_success(self, redis_client: RedisClient) -> None:
        """Test de agregar hechizo exitosamente."""
        repo = SpellbookRepository(redis_client)

        result = await repo.add_spell(user_id=1, slot=1, spell_id=10)

        assert result is True

        # Verificar que se guardó
        spell_id = await repo.get_spell_in_slot(1, 1)
        assert spell_id == 10

    async def test_add_spell_invalid_slot_low(self, redis_client: RedisClient) -> None:
        """Test de agregar hechizo con slot inválido (muy bajo)."""
        repo = SpellbookRepository(redis_client)

        result = await repo.add_spell(user_id=1, slot=0, spell_id=10)

        assert result is False

    async def test_add_spell_invalid_slot_high(self, redis_client: RedisClient) -> None:
        """Test de agregar hechizo con slot inválido (muy alto)."""
        repo = SpellbookRepository(redis_client)

        result = await repo.add_spell(user_id=1, slot=26, spell_id=10)

        assert result is False

    async def test_add_multiple_spells(self, redis_client: RedisClient) -> None:
        """Test de agregar múltiples hechizos."""
        repo = SpellbookRepository(redis_client)

        await repo.add_spell(user_id=1, slot=1, spell_id=10)
        await repo.add_spell(user_id=1, slot=2, spell_id=20)
        await repo.add_spell(user_id=1, slot=3, spell_id=30)

        spell1 = await repo.get_spell_in_slot(1, 1)
        spell2 = await repo.get_spell_in_slot(1, 2)
        spell3 = await repo.get_spell_in_slot(1, 3)

        assert spell1 == 10
        assert spell2 == 20
        assert spell3 == 30

    async def test_remove_spell_success(self, redis_client: RedisClient) -> None:
        """Test de eliminar hechizo exitosamente."""
        repo = SpellbookRepository(redis_client)

        # Agregar hechizo
        await repo.add_spell(user_id=1, slot=1, spell_id=10)

        # Eliminar hechizo
        result = await repo.remove_spell(user_id=1, slot=1)

        assert result is True

        # Verificar que se eliminó
        spell_id = await repo.get_spell_in_slot(1, 1)
        assert spell_id is None

    async def test_remove_spell_empty_slot(self, redis_client: RedisClient) -> None:
        """Test de eliminar hechizo de slot vacío."""
        repo = SpellbookRepository(redis_client)

        # Intentar eliminar de slot vacío
        result = await repo.remove_spell(user_id=1, slot=1)

        assert result is False

    async def test_get_spell_in_slot_exists(self, redis_client: RedisClient) -> None:
        """Test de obtener hechizo existente."""
        repo = SpellbookRepository(redis_client)

        await repo.add_spell(user_id=1, slot=5, spell_id=15)

        spell_id = await repo.get_spell_in_slot(1, 5)

        assert spell_id == 15

    async def test_get_spell_in_slot_empty(self, redis_client: RedisClient) -> None:
        """Test de obtener hechizo de slot vacío."""
        repo = SpellbookRepository(redis_client)

        spell_id = await repo.get_spell_in_slot(1, 1)

        assert spell_id is None

    async def test_get_all_spells_empty(self, redis_client: RedisClient) -> None:
        """Test de obtener todos los hechizos cuando está vacío."""
        repo = SpellbookRepository(redis_client)

        spells = await repo.get_all_spells(1)

        assert spells == {}

    async def test_get_all_spells_multiple(self, redis_client: RedisClient) -> None:
        """Test de obtener todos los hechizos con múltiples hechizos."""
        repo = SpellbookRepository(redis_client)

        await repo.add_spell(user_id=1, slot=1, spell_id=10)
        await repo.add_spell(user_id=1, slot=3, spell_id=30)
        await repo.add_spell(user_id=1, slot=5, spell_id=50)

        spells = await repo.get_all_spells(1)

        assert len(spells) == 3
        assert spells[1] == 10
        assert spells[3] == 30
        assert spells[5] == 50

    async def test_clear_spellbook_success(self, redis_client: RedisClient) -> None:
        """Test de limpiar libro de hechizos."""
        repo = SpellbookRepository(redis_client)

        # Agregar varios hechizos
        await repo.add_spell(user_id=1, slot=1, spell_id=10)
        await repo.add_spell(user_id=1, slot=2, spell_id=20)

        # Limpiar
        result = await repo.clear_spellbook(1)

        assert result is True

        # Verificar que está vacío
        spells = await repo.get_all_spells(1)
        assert spells == {}

    async def test_clear_spellbook_empty(self, redis_client: RedisClient) -> None:
        """Test de limpiar libro de hechizos vacío."""
        repo = SpellbookRepository(redis_client)

        result = await repo.clear_spellbook(1)

        assert result is True

    async def test_initialize_default_spells_new_user(self, redis_client: RedisClient) -> None:
        """Test de inicializar hechizos por defecto para usuario nuevo."""
        repo = SpellbookRepository(redis_client)

        result = await repo.initialize_default_spells(1)

        assert result is True

        # Verificar que tiene Dardo Mágico en slot 1
        spell_id = await repo.get_spell_in_slot(1, 1)
        assert spell_id == 1

    async def test_initialize_default_spells_existing_user(self, redis_client: RedisClient) -> None:
        """Test de inicializar hechizos cuando ya tiene hechizos."""
        repo = SpellbookRepository(redis_client)

        # Agregar un hechizo primero
        await repo.add_spell(user_id=1, slot=2, spell_id=99)

        # Intentar inicializar
        result = await repo.initialize_default_spells(1)

        assert result is True

        # Verificar que NO se agregó el Dardo Mágico (ya tenía hechizos)
        spell_id = await repo.get_spell_in_slot(1, 1)
        assert spell_id is None

        # Verificar que el hechizo original sigue ahí
        spell_id = await repo.get_spell_in_slot(1, 2)
        assert spell_id == 99

    async def test_get_spellbook_for_client_empty(self, redis_client: RedisClient) -> None:
        """Test de obtener libro para cliente cuando está vacío."""
        repo = SpellbookRepository(redis_client)

        result = await repo.get_spellbook_for_client(1)

        assert result == []

    async def test_get_spellbook_for_client_with_spells(self, redis_client: RedisClient) -> None:
        """Test de obtener libro para cliente con hechizos."""
        repo = SpellbookRepository(redis_client)

        await repo.add_spell(user_id=1, slot=3, spell_id=30)
        await repo.add_spell(user_id=1, slot=1, spell_id=10)
        await repo.add_spell(user_id=1, slot=2, spell_id=20)

        result = await repo.get_spellbook_for_client(1)

        # Debe estar ordenado por slot
        assert len(result) == 3
        assert result[0] == {"slot": 1, "spell_id": 10}
        assert result[1] == {"slot": 2, "spell_id": 20}
        assert result[2] == {"slot": 3, "spell_id": 30}

    async def test_different_users_isolated(self, redis_client: RedisClient) -> None:
        """Test de que los hechizos de diferentes usuarios están aislados."""
        repo = SpellbookRepository(redis_client)

        # Usuario 1
        await repo.add_spell(user_id=1, slot=1, spell_id=10)

        # Usuario 2
        await repo.add_spell(user_id=2, slot=1, spell_id=20)

        # Verificar que cada usuario tiene su propio hechizo
        spell_user1 = await repo.get_spell_in_slot(1, 1)
        spell_user2 = await repo.get_spell_in_slot(2, 1)

        assert spell_user1 == 10
        assert spell_user2 == 20

    async def test_overwrite_spell_in_slot(self, redis_client: RedisClient) -> None:
        """Test de sobrescribir hechizo en un slot."""
        repo = SpellbookRepository(redis_client)

        # Agregar hechizo
        await repo.add_spell(user_id=1, slot=1, spell_id=10)

        # Sobrescribir con otro hechizo
        await repo.add_spell(user_id=1, slot=1, spell_id=99)

        # Verificar que se sobrescribió
        spell_id = await repo.get_spell_in_slot(1, 1)
        assert spell_id == 99

    async def test_add_spell_boundary_slots(self, redis_client: RedisClient) -> None:
        """Test de agregar hechizos en slots límite (1 y 25)."""
        repo = SpellbookRepository(redis_client)

        # Slot mínimo
        result1 = await repo.add_spell(user_id=1, slot=1, spell_id=10)
        assert result1 is True

        # Slot máximo
        result25 = await repo.add_spell(user_id=1, slot=25, spell_id=99)
        assert result25 is True

        # Verificar
        spell1 = await repo.get_spell_in_slot(1, 1)
        spell25 = await repo.get_spell_in_slot(1, 25)

        assert spell1 == 10
        assert spell25 == 99

    async def test_add_spell_redis_none(self) -> None:
        """Test de agregar hechizo cuando Redis no está disponible."""
        redis_client = MagicMock()
        redis_client.redis = None

        repo = SpellbookRepository(redis_client)

        result = await repo.add_spell(user_id=1, slot=1, spell_id=10)

        assert result is False

    async def test_remove_spell_redis_none(self) -> None:
        """Test de eliminar hechizo cuando Redis no está disponible."""
        redis_client = MagicMock()
        redis_client.redis = None

        repo = SpellbookRepository(redis_client)

        result = await repo.remove_spell(user_id=1, slot=1)

        assert result is False

    async def test_get_spell_in_slot_redis_none(self) -> None:
        """Test de obtener hechizo cuando Redis no está disponible."""
        redis_client = MagicMock()
        redis_client.redis = None

        repo = SpellbookRepository(redis_client)

        result = await repo.get_spell_in_slot(user_id=1, slot=1)

        assert result is None

    async def test_get_all_spells_redis_none(self) -> None:
        """Test de obtener todos los hechizos cuando Redis no está disponible."""
        redis_client = MagicMock()
        redis_client.redis = None

        repo = SpellbookRepository(redis_client)

        result = await repo.get_all_spells(1)

        assert result == {}

    async def test_clear_spellbook_redis_none(self) -> None:
        """Test de limpiar libro cuando Redis no está disponible."""
        redis_client = MagicMock()
        redis_client.redis = None

        repo = SpellbookRepository(redis_client)

        result = await repo.clear_spellbook(1)

        assert result is False
