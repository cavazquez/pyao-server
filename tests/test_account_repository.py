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
