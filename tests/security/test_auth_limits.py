"""Límites con reloj controlado y cierre de sesiones pendientes de login."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.command_handlers.login_handler import LoginCommandHandler
from src.commands.login_command import LoginCommand
from src.config.game_config import SecurityConfig
from src.security.auth_limits import AuthLimiter, ConnectionAttempts
from src.server import ArgentumServer


def test_limits_reconnect_case_and_window_recovery():
    """Reconectar o alternar mayúsculas no recupera presupuesto de cuenta/IP."""
    now = [0.0]
    limits = AuthLimiter(
        SecurityConfig(
            auth_attempts_per_connection=2, auth_attempts_per_ip=3, auth_attempts_per_account=2
        ),
        lambda: now[0],
    )
    first = ConnectionAttempts()
    assert limits.allow("127.0.0.1", "Usuario", first)
    assert limits.allow("127.0.0.1", "OtraCuenta", first)
    assert not limits.allow("127.0.0.1", "Tercera", first)
    assert limits.allow("127.0.0.1", "uSUArio", ConnectionAttempts())
    assert not limits.allow("127.0.0.2", "usuario", ConnectionAttempts())
    assert not limits.allow("127.0.0.1", "Cuarta", ConnectionAttempts())
    now[0] = 60.0
    assert limits.allow("127.0.0.1", "Usuario", first)


def test_spray_does_not_evict_live_counters_or_grow_memory():
    """La memoria se acota sin permitir eludir límites desalojando otras claves."""
    limits = AuthLimiter(SecurityConfig(auth_max_keys=2), lambda: 0.0)
    assert limits.allow("127.0.0.1", "Usuario", ConnectionAttempts())
    for number in range(50):
        assert not limits.allow(f"127.0.1.{number}", f"Nuevo{number}", ConnectionAttempts())
    assert len(limits._ips) + len(limits._accounts) == 2


@pytest.mark.asyncio
async def test_expired_auth_deadline_closes_connection_and_releases_place():
    """Una sesión silenciosa expirada se cierra sin esperar datos adicionales."""
    server = ArgentumServer()
    server.auth_timeout_seconds = 0
    reader = MagicMock()

    async def waiting_read(_size):
        await asyncio.Event().wait()

    reader.read = AsyncMock(side_effect=waiting_read)
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 1234)
    writer.wait_closed = AsyncMock()
    with patch.object(server, "create_task") as factory:
        await asyncio.wait_for(server.handle_client(reader, writer), timeout=1)
        factory.assert_not_called()
    assert server._active_connections == 0
    writer.close.assert_called_once()


@pytest.mark.asyncio
async def test_denied_login_never_reaches_password_verification():
    """La barrera se aplica antes de consultar o verificar una cuenta."""
    handler = LoginCommandHandler.__new__(LoginCommandHandler)
    handler.auth_handler = MagicMock()
    handler.auth_handler.authenticate_user = AsyncMock()
    handler.message_sender = MagicMock()
    handler.message_sender.send_error_msg = AsyncMock()
    handler.message_sender.connection.allow_authentication.return_value = False
    canary = "Synthetic100"
    result = await handler.handle(LoginCommand(username="Synthetic", password=canary))
    assert not result.success
    handler.auth_handler.authenticate_user.assert_not_awaited()
    handler.message_sender.send_error_msg.assert_awaited_once_with(
        "Usuario o contraseña incorrectos"
    )
