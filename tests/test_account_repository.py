"""Tests directos para AccountRepository."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.account_repository import AccountRepository


@pytest.mark.asyncio
class TestAccountRepository:
    """Tests para AccountRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = MagicMock()
        repo = AccountRepository(redis_client)

        assert repo.redis == redis_client

    async def test_create_account_duplicate(self) -> None:
        """Test de creación de cuenta duplicada."""
        redis_client = MagicMock()
        redis_client.redis.get = AsyncMock(return_value=b"1")  # Ya existe

        repo = AccountRepository(redis_client)

        with pytest.raises(ValueError, match="ya existe"):
            await repo.create_account("testuser", "hash123", "test@example.com")

    async def test_create_account_success(self) -> None:
        """Test de creación de cuenta exitosa."""
        redis_client = MagicMock()
        redis_client.redis.get = AsyncMock(return_value=None)  # No existe
        redis_client.redis.incr = AsyncMock(return_value=1)
        redis_client.redis.set = AsyncMock()
        redis_client.redis.hset = AsyncMock()

        repo = AccountRepository(redis_client)
        user_id = await repo.create_account("newuser", "hash123", "new@example.com")

        assert user_id == 1
        redis_client.redis.incr.assert_called_once()
        redis_client.redis.set.assert_called_once()
        redis_client.redis.hset.assert_called_once()

    async def test_create_account_with_char_data(self) -> None:
        """Test de creación de cuenta con datos de personaje."""
        redis_client = MagicMock()
        redis_client.redis.get = AsyncMock(return_value=None)
        redis_client.redis.incr = AsyncMock(return_value=2)
        redis_client.redis.set = AsyncMock()
        redis_client.redis.hset = AsyncMock()

        repo = AccountRepository(redis_client)
        char_data = {"race": 1, "gender": 1, "job": 1, "head": 18, "home": 1}
        user_id = await repo.create_account("charuser", "hash123", "char@example.com", char_data)

        assert user_id == 2

    async def test_get_account_found(self) -> None:
        """Test de obtención de cuenta existente."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(
            return_value={
                "user_id": "1",
                "username": "testuser",
                "password_hash": "hash123",
                "email": "test@example.com",
            }
        )

        repo = AccountRepository(redis_client)
        account = await repo.get_account("testuser")

        assert account is not None
        assert account["user_id"] == "1"
        assert account["username"] == "testuser"

    async def test_get_account_not_found(self) -> None:
        """Test de obtención de cuenta no existente."""
        redis_client = MagicMock()
        redis_client.redis.hgetall = AsyncMock(return_value={})

        repo = AccountRepository(redis_client)
        account = await repo.get_account("nonexistent")

        assert account is None
