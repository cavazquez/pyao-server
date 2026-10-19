"""Tests directos para AccountRepository."""

from unittest.mock import AsyncMock

import pytest

from src.repositories.account_repository import AccountRepository
from src.utils.redis_config import RedisKeys
from tests.conftest import create_mock_redis_client


@pytest.mark.asyncio
class TestAccountRepository:
    """Tests para AccountRepository."""

    async def test_init(self) -> None:
        """Test de inicialización."""
        redis_client = create_mock_redis_client()
        repo = AccountRepository(redis_client)

        assert repo.redis == redis_client

    async def test_create_account_duplicate(self, redis_client) -> None:
        """Una segunda alta no sobrescribe una cuenta existente."""
        repo = AccountRepository(redis_client)
        user_id = await repo.create_account("testuser", "hash123", "test@example.com")
        with pytest.raises(ValueError, match="ya existe"):
            await repo.create_account("testuser", "other-hash", "other@example.com")
        account = await repo.get_account_by_user_id(user_id)
        assert account["password_hash"] == "hash123"

    async def test_create_account_success(self, redis_client) -> None:
        """Perfil, índice directo y reloj fiscal nacen juntos."""
        repo = AccountRepository(redis_client)
        user_id = await repo.create_account("newuser", "hash123", "new@example.com")
        assert user_id == 1
        assert await redis_client.get(RedisKeys.account_id_by_username("newuser")) == str(user_id)
        assert await redis_client.hget("account:index:user_id", str(user_id)) == "newuser"
        assert (await repo.get_account("newuser"))["user_id"] == str(user_id)
        assert await redis_client.hget(f"tax:{user_id}:state", "total_paid") == "0"

    async def test_create_account_with_char_data(self, redis_client) -> None:
        """La transacción conserva los datos nativos de creación de personaje."""
        await redis_client.set(RedisKeys.ACCOUNTS_COUNTER, "1")
        repo = AccountRepository(redis_client)
        char_data = {"race": 1, "gender": 1, "job": 1, "head": 18, "home": 1}
        user_id = await repo.create_account("charuser", "hash123", "char@example.com", char_data)
        assert user_id == 2
        assert (await repo.get_account("charuser"))["char_head"] == "18"

    async def test_get_account_found(self) -> None:
        """Test de obtención de cuenta existente."""
        redis_client = create_mock_redis_client()
        redis_client.hgetall = AsyncMock(
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
        redis_client = create_mock_redis_client()
        redis_client.hgetall = AsyncMock(return_value={})

        repo = AccountRepository(redis_client)
        account = await repo.get_account("nonexistent")

        assert account is None
