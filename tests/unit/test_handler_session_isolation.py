"""Regresiones de sesiones intercaladas atendidas por el mismo TaskFactory."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.commands.base import Command, CommandHandler, CommandResult
from src.tasks.handler_registry import HANDLER_CONFIGS, HandlerConfig, HandlerRegistry
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_login import TaskLogin


class SuspendedLogin(CommandHandler):
    """Simula un login suspendido mientras otro cliente solicita el mismo handler."""

    def __init__(self, message_sender, session_data) -> None:
        """Conserva las dependencias de la petición hasta completar su await."""
        self.message_sender = message_sender
        self.session_data = session_data

    async def handle(self, command: Command) -> CommandResult:
        await command.entered.wait()
        await command.release.wait()
        self.session_data["user_id"] = command.user_id
        await self.message_sender.send_error_msg("respuesta privada")
        return CommandResult.ok()


@pytest.mark.asyncio
@pytest.mark.parametrize("disconnected", [False, True])
async def test_suspended_login_cannot_write_another_connection(monkeypatch, disconnected):
    """B no cambia el emisor ni la sesión de A mientras su autenticación está pendiente."""
    monkeypatch.setitem(
        HANDLER_CONFIGS, "isolated_login", HandlerConfig(SuspendedLogin, needs_session_data=True)
    )
    registry = HandlerRegistry(Mock())
    sender_a, sender_b = AsyncMock(), AsyncMock()
    if disconnected:
        sender_a.send_error_msg.side_effect = ConnectionError("A desconectado")
    session_a, session_b = {}, {}
    handler_a = registry.get("isolated_login", sender_a, session_a)
    entered, release = asyncio.Event(), asyncio.Event()
    task = asyncio.create_task(
        handler_a.handle(SimpleNamespace(entered=entered, release=release, user_id=41))
    )
    entered.set()
    await asyncio.sleep(0)
    handler_b = registry.get("isolated_login", sender_b, session_b)
    assert handler_a is not handler_b
    release.set()
    if disconnected:
        with pytest.raises(ConnectionError):
            await task
    else:
        await task
    assert session_a == {"user_id": 41}
    assert session_b == {}
    sender_a.send_error_msg.assert_awaited_once_with("respuesta privada")
    sender_b.send_error_msg.assert_not_awaited()


def test_walk_subhandlers_keep_their_own_sender():
    """Los subhandlers de validación y movimiento no conservan el emisor anterior."""
    registry = HandlerRegistry(Mock())
    sender_a, sender_b = Mock(), Mock()
    first = registry.get("walk", sender_a, {})
    second = registry.get("walk", sender_b, {})
    assert first is not second
    for handler, sender in ((first, sender_a), (second, sender_b)):
        assert handler.message_sender is sender
        assert handler.validation_handler.message_sender is sender
        assert handler.movement_handler.message_sender is sender


def test_real_login_subhandlers_and_session_identity():
    """El login real conserva todas sus dependencias de conexión."""
    registry = HandlerRegistry(Mock())
    sender_a, sender_b = Mock(), Mock()
    session_a, session_b = {}, {}
    first = registry.get("login", sender_a, session_a)
    second = registry.get("login", sender_b, session_b)
    assert first.session_data is session_a
    assert second.session_data is session_b
    for handler, sender in ((first, sender_a), (second, sender_b)):
        for subhandler in (
            handler.auth_handler,
            handler.init_handler,
            handler.spawn_handler,
            handler.finalization_handler,
        ):
            assert subhandler.message_sender is sender


@pytest.mark.parametrize("name", ["login", "create_account"])
def test_initially_empty_session_is_kept_through_authentication(name):
    """Un alta sin tirada previa no publica el login en un diccionario descartado."""
    registry = HandlerRegistry(Mock())
    session = {}
    handler = registry.get(name, Mock(), session)
    assert handler.session_data is session
    if name == "create_account":
        assert handler.finalization_handler.session_data is session
    for task_type in [TaskLogin, TaskCreateAccount]:
        assert task_type(b"", Mock(), session_data=session).session_data is session
