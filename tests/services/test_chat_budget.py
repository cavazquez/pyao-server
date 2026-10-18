"""Presupuesto de todos los canales, avisos y comandos de control."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.packet_id import ClientPacketID
from src.operations.two_client_smoke import minimum_dependencies
from src.services.chat_budget import ChatBudget
from src.tasks.task_chat_limited import TaskChatLimited
from src.tasks.task_factory import TaskFactory


def packet(packet_id, message="hola"):
    """Construye mensajes con el codec canónico, sin heurísticas por read TCP."""
    values = ["Bob", message] if packet_id == ClientPacketID.WHISPER else [message]
    return bytes([packet_id]) + b"".join(
        struct.pack("<H", len(value.encode("latin-1"))) + value.encode("latin-1")
        for value in values
    )


def test_channels_share_tokens_and_users_are_independent_without_wall_clock():
    """Cambiar de canal o reconectar no entrega otro burst."""
    now = [100.0]
    budget = ChatBudget(clock=lambda: now[0])
    channels = [
        ClientPacketID.TALK,
        ClientPacketID.YELL,
        ClientPacketID.WHISPER,
        ClientPacketID.PARTY_MESSAGE,
        ClientPacketID.TALK,
    ]
    for channel in channels:
        assert budget.gate(1, packet(channel)) == (True, False)
    assert budget.gate(1, packet(ClientPacketID.WHISPER)) == (False, True)
    assert budget.gate(1, packet(ClientPacketID.PARTY_MESSAGE)) == (False, False)
    assert budget.gate(2, packet(ClientPacketID.TALK)) == (True, False)
    now[0] += 0.999
    assert budget.gate(1, packet(ClientPacketID.TALK)) == (False, False)
    now[0] += 0.001001
    assert budget.gate(1, packet(ClientPacketID.TALK)) == (True, False)
    assert budget.gate(1, packet(ClientPacketID.TALK)) == (False, False)


def test_essential_commands_and_control_packets_survive_chat_limit():
    """La lista es exacta: un slash arbitrario no elude el presupuesto."""
    budget = ChatBudget(clock=lambda: 100.0)
    for _ in range(5):
        budget.gate(1, packet(ClientPacketID.TALK))
    for command in ["/METRICS", "/SALIRCLAN", "/RECHAZARCLAN", "/LIBERAR"]:
        assert budget.gate(1, packet(ClientPacketID.TALK, command)) == (True, False)
    for command in ["/METRICSotra", " /METRICS", "/inventado"]:
        assert budget.gate(1, packet(ClientPacketID.TALK, command))[0] is False
    for control in [ClientPacketID.PING, ClientPacketID.QUIT, ClientPacketID.CAPABILITIES]:
        assert budget.gate(1, bytes([control])) is None


def test_oversize_messages_and_warning_flood_are_bounded():
    """Un texto grande no llega al handler y cien rechazos producen un solo aviso."""
    now = [100.0]
    budget = ChatBudget(clock=lambda: now[0])
    oversized = packet(ClientPacketID.TALK, "ñ" * 513)
    assert sum(budget.gate(1, oversized)[1] for _ in range(100)) == 1
    now[0] += 5.0
    assert budget.gate(1, oversized) == (False, True)
    now[0] += 301.0
    assert budget.gate(2, packet(ClientPacketID.TALK))[0]
    assert budget.gate(1, packet(ClientPacketID.TALK))[0]


@pytest.mark.asyncio
async def test_factory_applies_shared_budget_before_constructing_chat_handlers(redis_client):
    """Dos factories de la misma sesión no generan cuotas separadas ni consultas extra."""
    deps = minimum_dependencies(redis_client)
    deps.chat_budget = ChatBudget(clock=lambda: 100.0)
    first, second = TaskFactory(deps), TaskFactory(deps)
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    for _ in range(5):
        assert not isinstance(
            first.create_task(packet(ClientPacketID.TALK), sender, {"user_id": 1}), TaskChatLimited
        )
    for _ in range(100):
        task = second.create_task(packet(ClientPacketID.PARTY_MESSAGE), sender, {"user_id": 1})
        assert isinstance(task, TaskChatLimited)
        await task.execute()
    assert sender.send_console_msg.await_count == 1
    assert not isinstance(
        second.create_task(packet(ClientPacketID.TALK), sender, {"user_id": 2}), TaskChatLimited
    )
    assert not isinstance(
        first.create_task(bytes([ClientPacketID.PING]), sender, {"user_id": 1}), TaskChatLimited
    )
