"""Tests para AuthenticationService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.message_sender import MessageSender
from src.network.client_connection import ClientConnection
from src.repositories.account_repository import AccountRepository
from src.services.player.authentication_service import AuthenticationService


@pytest.mark.asyncio
async def test_authenticate_success():
    """Verifica autenticación exitosa."""
    # Mock del writer
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    # Mock del account_repo
    account_repo = MagicMock(spec=AccountRepository)
    account_repo.get_account = AsyncMock(
        return_value={
            "user_id": 123,
            "char_job": 2,
        }
    )
    account_repo.verify_password = AsyncMock(return_value=True)

    # Crear conexión y message sender
    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Crear servicio
    auth_service = AuthenticationService(account_repo, message_sender)

    # Autenticar
    result = await auth_service.authenticate("testuser", "password123")

    # Verificar resultado
    assert result is not None
    assert result == (123, 2)

    # Verificar que no se envió error
    assert writer.write.call_count == 0


@pytest.mark.asyncio
async def test_authenticate_user_not_found():
    """Verifica rechazo cuando el usuario no existe."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    account_repo = MagicMock(spec=AccountRepository)
    account_repo.get_account = AsyncMock(return_value=None)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    auth_service = AuthenticationService(account_repo, message_sender)

    result = await auth_service.authenticate("nonexistent", "password123")

    # Verificar que falló
    assert result is None

    # Verificar que se envió error
    assert writer.write.call_count == 1
    sent_data = writer.write.call_args[0][0]
    # Verificar que es un paquete de error (ErrorMsg)
    assert len(sent_data) > 0


@pytest.mark.asyncio
async def test_authenticate_wrong_password():
    """Verifica rechazo con contraseña incorrecta."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    account_repo = MagicMock(spec=AccountRepository)
    account_repo.get_account = AsyncMock(
        return_value={
            "user_id": 123,
            "char_job": 2,
        }
    )
    account_repo.verify_password = AsyncMock(return_value=False)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    auth_service = AuthenticationService(account_repo, message_sender)

    result = await auth_service.authenticate("testuser", "wrongpassword")

    # Verificar que falló
    assert result is None

    # Verificar que se envió error
    assert writer.write.call_count == 1


@pytest.mark.asyncio
async def test_authenticate_repo_not_available():
    """Verifica manejo cuando el repositorio no está disponible."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    message_sender = MessageSender(connection)

    # Crear servicio con repo None
    auth_service = AuthenticationService(None, message_sender)  # type: ignore[arg-type]

    result = await auth_service.authenticate("testuser", "password123")

    # Verificar que falló
    assert result is None

    # Verificar que se envió error
    assert writer.write.call_count == 1
