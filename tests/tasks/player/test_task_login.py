"""Tests para TaskLogin."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.commands.login_command import LoginCommand
from src.tasks.player.task_login import TaskLogin


@pytest.mark.asyncio
class TestTaskLogin:
    """Tests para TaskLogin."""

    async def test_parse_packet_valid(self) -> None:
        """Test de parseo de packet válido."""
        username = "testuser"
        password = "password123"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")

        data = (
            bytes([0x03])  # PacketID LOGIN
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
        )

        message_sender = MagicMock()
        task = TaskLogin(data, message_sender)

        result = task._parse_packet()

        assert result is not None
        assert result[0] == username
        assert result[1] == password

    async def test_parse_packet_invalid(self) -> None:
        """Test de parseo de packet inválido."""
        data = bytes([0x03])  # Solo PacketID, sin datos

        message_sender = MagicMock()
        task = TaskLogin(data, message_sender)

        result = task._parse_packet()

        assert result is None

    async def test_execute_invalid_packet(self) -> None:
        """Test de execute con packet inválido."""
        data = bytes([0x03])  # Packet inválido

        message_sender = MagicMock()
        message_sender.connection.address = "127.0.0.1:1234"

        task = TaskLogin(data, message_sender)

        await task.execute()

        # No debe hacer nada más (no debe llamar al handler)

    async def test_execute_success(self) -> None:
        """Test de execute exitoso."""
        username = "testuser"
        password = "password123"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")

        data = (
            bytes([0x03])  # PacketID LOGIN
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
        )

        message_sender = MagicMock()
        login_handler = MagicMock()
        login_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                data={"user_id": 1, "username": username, "user_class": 2}
            )
        )

        task = TaskLogin(data, message_sender, login_handler=login_handler)

        await task.execute()

        # Verificar que se llamó al handler con el comando correcto
        login_handler.handle.assert_called_once()
        call_args = login_handler.handle.call_args[0][0]
        assert isinstance(call_args, LoginCommand)
        assert call_args.username == username
        assert call_args.password == password

    async def test_execute_handler_not_available(self) -> None:
        """Test de execute cuando el handler no está disponible."""
        username = "testuser"
        password = "password123"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")

        data = (
            bytes([0x03])  # PacketID LOGIN
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
        )

        message_sender = MagicMock()
        message_sender.send_error_msg = AsyncMock()

        task = TaskLogin(data, message_sender, login_handler=None)

        await task.execute()

        # Debe enviar error al cliente
        message_sender.send_error_msg.assert_called_once_with("Servicio no disponible")

    async def test_execute_with_credentials_success(self) -> None:
        """Test de execute_with_credentials exitoso."""
        username = "testuser"
        password = "password123"

        message_sender = MagicMock()
        login_handler = MagicMock()
        login_handler.handle = AsyncMock(
            return_value=CommandResult.ok(
                data={"user_id": 1, "username": username, "user_class": 2}
            )
        )

        task = TaskLogin(bytes([0x03]), message_sender, login_handler=login_handler)

        await task.execute_with_credentials(username, password)

        # Verificar que se llamó al handler con el comando correcto
        login_handler.handle.assert_called_once()
        call_args = login_handler.handle.call_args[0][0]
        assert isinstance(call_args, LoginCommand)
        assert call_args.username == username
        assert call_args.password == password

    async def test_execute_with_credentials_handler_not_available(self) -> None:
        """Test de execute_with_credentials cuando el handler no está disponible."""
        username = "testuser"
        password = "password123"

        message_sender = MagicMock()
        message_sender.send_error_msg = AsyncMock()

        task = TaskLogin(bytes([0x03]), message_sender, login_handler=None)

        await task.execute_with_credentials(username, password)

        # Debe enviar error al cliente
        message_sender.send_error_msg.assert_called_once_with("Servicio no disponible")

    async def test_execute_handler_error(self) -> None:
        """Test de execute cuando el handler retorna error."""
        username = "testuser"
        password = "password123"

        username_bytes = username.encode("utf-8")
        password_bytes = password.encode("utf-8")

        data = (
            bytes([0x03])  # PacketID LOGIN
            + struct.pack("<H", len(username_bytes))
            + username_bytes
            + struct.pack("<H", len(password_bytes))
            + password_bytes
        )

        message_sender = MagicMock()
        login_handler = MagicMock()
        login_handler.handle = AsyncMock(return_value=CommandResult.error("Autenticación fallida"))

        task = TaskLogin(data, message_sender, login_handler=login_handler)

        await task.execute()

        # Verificar que se llamó al handler
        login_handler.handle.assert_called_once()
        call_args = login_handler.handle.call_args[0][0]
        assert isinstance(call_args, LoginCommand)
        assert call_args.username == username
        assert call_args.password == password
