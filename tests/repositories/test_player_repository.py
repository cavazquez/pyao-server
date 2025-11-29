"""Tests para PlayerRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.repositories.player_repository import PlayerRepository


@pytest.mark.asyncio
class TestPlayerRepository:
    """Tests para PlayerRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        repo = PlayerRepository(redis_client)

        assert repo.redis == redis_client

    async def test_get_gold(self) -> None:
        """Test de obtención de oro."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={"gold": "1000", "level": "1", "min_hp": "100", "max_hp": "100"}
        )

        repo = PlayerRepository(redis_client)
        gold = await repo.get_gold(1)

        assert gold == 1000

    async def test_get_gold_not_found(self) -> None:
        """Test de obtención de oro cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = PlayerRepository(redis_client)
        gold = await repo.get_gold(1)

        assert gold == 0

    async def test_update_gold(self) -> None:
        """Test de actualización de oro."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_gold(1, 500)

        redis_client.redis.hset.assert_called_once()

    async def test_update_hp(self) -> None:
        """Test de actualización de HP."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_hp(1, 50)

        redis_client.redis.hset.assert_called_once()

    async def test_update_experience(self) -> None:
        """Test de actualización de experiencia."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_experience(1, 1000)

        redis_client.redis.hset.assert_called_once()

    async def test_get_position(self) -> None:
        """Test de obtención de posición."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                b"x": b"50",
                b"y": b"50",
                b"map": b"1",
                b"heading": b"3",
            }
        )

        repo = PlayerRepository(redis_client)
        position = await repo.get_position(1)

        assert position is not None
        assert position["x"] == 50
        assert position["y"] == 50
        assert position["map"] == 1

    async def test_get_position_not_found(self) -> None:
        """Test de obtención de posición cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = PlayerRepository(redis_client)
        position = await repo.get_position(1)

        assert position is None

    async def test_set_position(self) -> None:
        """Test de configuración de posición."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_position(1, 50, 50, 1, 3)

        redis_client.redis.hset.assert_called_once()

    async def test_set_position_without_heading(self) -> None:
        """Test de configuración de posición sin heading."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_position(1, 60, 70, 2)

        redis_client.redis.hset.assert_called_once()

    async def test_set_heading(self) -> None:
        """Test de configuración de heading."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_heading(1, 2)

        redis_client.redis.hset.assert_called_once()

    async def test_get_stats(self) -> None:
        """Test de obtención de stats."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "min_hp": "100",
                "max_hp": "100",
                "min_mana": "50",
                "max_mana": "50",
                "min_sta": "100",
                "max_sta": "100",
                "gold": "1000",
                "level": "1",
                "experience": "0",
            }
        )

        repo = PlayerRepository(redis_client)
        stats = await repo.get_stats(1)

        assert stats is not None
        assert stats["min_hp"] == 100
        assert stats["max_hp"] == 100
        assert stats["gold"] == 1000
        assert stats["level"] == 1

    async def test_get_stats_not_found(self) -> None:
        """Test de obtención de stats cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = PlayerRepository(redis_client)
        stats = await repo.get_stats(1)

        assert stats is None

    async def test_set_stats(self) -> None:
        """Test de configuración de stats."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_stats(
            user_id=1,
            min_hp=100,
            max_hp=100,
            min_mana=50,
            max_mana=50,
            min_sta=100,
            max_sta=100,
            gold=1000,
            level=1,
            elu=300,
            experience=0,
        )

        redis_client.redis.hset.assert_called_once()

    async def test_get_hunger_thirst(self) -> None:
        """Test de obtención de hambre y sed."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "min_hunger": "50",
                "max_hunger": "100",
                "min_water": "50",
                "max_water": "100",
            }
        )

        repo = PlayerRepository(redis_client)
        hunger_thirst = await repo.get_hunger_thirst(1)

        assert hunger_thirst is not None
        # Los valores por defecto se aplican si no existen
        assert hunger_thirst["min_hunger"] == 50
        assert hunger_thirst["max_hunger"] == 100
        assert hunger_thirst["min_water"] == 50
        assert hunger_thirst["max_water"] == 100

    async def test_get_hunger_thirst_not_found(self) -> None:
        """Test de obtención de hambre y sed cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = PlayerRepository(redis_client)
        hunger_thirst = await repo.get_hunger_thirst(1)

        assert hunger_thirst is None

    async def test_set_hunger_thirst(self) -> None:
        """Test de configuración de hambre y sed."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_hunger_thirst(
            user_id=1,
            min_hunger=50,
            max_hunger=100,
            min_water=50,
            max_water=100,
            hunger_counter=0,
            water_counter=0,
            hunger_flag=0,
            thirst_flag=0,
        )

        redis_client.redis.hset.assert_called_once()

    async def test_get_attributes(self) -> None:
        """Test de obtención de atributos."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "strength": "18",
                "agility": "18",
                "intelligence": "18",
                "charisma": "18",
                "constitution": "18",
            }
        )
        # Mock para modificadores (no hay modificadores activos)
        redis_client.redis.hget = AsyncMock(return_value=None)

        repo = PlayerRepository(redis_client)
        attributes = await repo.get_attributes(1)

        assert attributes is not None
        assert attributes["strength"] == 18
        assert attributes["agility"] == 18
        assert attributes["intelligence"] == 18

    async def test_get_attributes_not_found(self) -> None:
        """Test de obtención de atributos cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = PlayerRepository(redis_client)
        attributes = await repo.get_attributes(1)

        assert attributes is None

    async def test_set_attributes(self) -> None:
        """Test de configuración de atributos."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_attributes(
            user_id=1,
            strength=18,
            agility=18,
            intelligence=18,
            charisma=18,
            constitution=18,
        )

        redis_client.redis.hset.assert_called_once()

    async def test_set_meditating(self) -> None:
        """Test de configuración de meditación."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.set_meditating(1, is_meditating=True)

        redis_client.redis.hset.assert_called_once()

    async def test_is_meditating_true(self) -> None:
        """Test de verificación de meditación (True)."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=b"1")  # Redis guarda "1" para True

        repo = PlayerRepository(redis_client)
        is_meditating = await repo.is_meditating(1)

        assert is_meditating is True

    async def test_is_meditating_false(self) -> None:
        """Test de verificación de meditación (False)."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=b"0")  # Redis guarda "0" para False

        repo = PlayerRepository(redis_client)
        is_meditating = await repo.is_meditating(1)

        assert is_meditating is False

    async def test_is_meditating_not_found(self) -> None:
        """Test de verificación de meditación cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hget = AsyncMock(return_value=None)

        repo = PlayerRepository(redis_client)
        is_meditating = await repo.is_meditating(1)

        assert is_meditating is False

    async def test_get_stamina(self) -> None:
        """Test de obtención de stamina."""
        redis_client = MagicMock()
        redis_client.redis.hmget = AsyncMock(return_value=[b"80", b"100"])

        repo = PlayerRepository(redis_client)
        min_sta, max_sta = await repo.get_stamina(1)

        assert min_sta == 80
        assert max_sta == 100

    async def test_get_stamina_not_found(self) -> None:
        """Test de obtención de stamina cuando no existe."""
        redis_client = MagicMock()
        redis_client.redis.hmget = AsyncMock(return_value=[None, None])

        repo = PlayerRepository(redis_client)
        min_sta, max_sta = await repo.get_stamina(1)

        assert min_sta == 100  # Valor por defecto
        assert max_sta == 100  # Valor por defecto

    async def test_update_stamina(self) -> None:
        """Test de actualización de stamina."""
        redis_client = MagicMock()
        redis_client.redis.hset = AsyncMock()

        repo = PlayerRepository(redis_client)
        await repo.update_stamina(1, 90)

        redis_client.redis.hset.assert_called_once()
