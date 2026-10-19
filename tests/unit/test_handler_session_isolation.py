"""Regresiones de sesiones intercaladas atendidas por el mismo TaskFactory."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.commands.base import Command, CommandHandler, CommandResult
from src.network.request_context import RequestContext
from src.tasks.handler_registry import HANDLER_CONFIGS, HandlerConfig, HandlerRegistry
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_login import TaskLogin


@pytest.mark.parametrize("name", sorted(HANDLER_CONFIGS))
def test_production_registry_can_construct_every_handler(name):
    """Un comando anunciado nunca falla por argumentos ausentes o incompatibles."""
    registry = HandlerRegistry(Mock())
    first = registry.get(name, Mock(), {"user_id": 1})
    second = registry.get(name, Mock(), {"user_id": 2})
    assert isinstance(first, HANDLER_CONFIGS[name].handler_class)
    assert first is not second


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


def test_context_observes_authentication_without_copying_the_session():
    """El contexto previo a login consulta la misma sesión después de autenticar."""
    sender, session = Mock(), {}
    context = RequestContext(sender, session)
    assert context.user_id is None
    session["user_id"] = 42
    assert context.user_id == 42
    assert context.sender is sender
    assert context.session is session


def test_registry_rejects_a_missing_dependency_before_execution():
    """Un wiring incompleto nombra el handler y la dependencia ausente."""
    deps = SimpleNamespace()
    with pytest.raises(ValueError, match=r"WalkCommandHandler\.action_cadence"):
        HandlerRegistry(deps).get("walk", Mock(), {})


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


@pytest.mark.parametrize("name", ["talk", "yell", "whisper"])
def test_chat_handlers_receive_request_session(name):
    """La sesión del chat procede de la petición, nunca del contenedor compartido."""
    deps = Mock()
    registry = HandlerRegistry(deps)
    session_a, session_b = {}, {"user_id": 2}
    first = registry.get(name, Mock(), session_a)
    second = registry.get(name, Mock(), session_b)
    assert first.session_data is session_a
    assert second.session_data is session_b


def test_talk_receives_real_world_services():
    """El wiring de producción no deja deshabilitados trade, clanes ni mascotas."""
    deps = Mock()
    handler = HandlerRegistry(deps).get("talk", Mock(), {})
    assert handler.trade_handler.trade_service is deps.trade_service
    assert handler.clan_handler.clan_service is deps.clan_service
    assert handler.pet_handler.npc_service is deps.npc_service
    assert handler.pet_handler.summon_service is deps.summon_service


def test_attack_defers_rewards_to_the_death_service():
    """Producción liquida XP/party una vez; el fallback conserva su concesión directa."""
    deps = Mock()
    assert HandlerRegistry(deps).get("attack", Mock()).execution_handler.defer_rewards is True
    deps.npc_death_service = None
    assert HandlerRegistry(deps).get("attack", Mock()).execution_handler.defer_rewards is False


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
