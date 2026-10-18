"""Extensiones optativas aisladas, posteriores al login y sin alterar legacy."""

import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.capabilities import Capability, ConnectionCapabilities
from src.network.client_connection import ClientConnection
from src.network.msg_map import build_change_map_response
from src.network.msg_session import build_logged_response
from src.tasks.task_capabilities import TaskCapabilities


def connection() -> ClientConnection:
    """Crea una conexión real con salida observable y sin servicios persistidos.

    Returns:
        Conexión con un writer de prueba que conserva el orden.
    """
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    return ClientConnection(MagicMock(), writer)


def test_only_requested_supported_bits_are_enabled_after_authentication() -> None:
    """Antes de autenticar, tarde o con versión/máscara inválida nunca habilita bits."""
    now = [100.0]
    state = ConnectionCapabilities(supported=Capability.SKILLS_CATALOG, clock=lambda: now[0])
    assert state.negotiate(1, 255) is None
    state.after_login()
    assert state.negotiate(2, 255) is None
    assert state.negotiate(1, -1) is None
    assert state.negotiate(1, 2) == 0
    assert state.negotiate(1, 255) == 0  # No se amplía una negociación ya aceptada.
    state.after_login()
    assert state.negotiate(1, 255) == 1
    state.clear()
    assert state.enabled == 0
    state.after_login()
    now[0] += 11
    assert state.negotiate(1, 255) is None
    assert state.enabled == 0


@pytest.mark.asyncio
async def test_legacy_and_extended_connections_keep_separate_streams() -> None:
    """La conexión legacy recibe exactamente Logged+ChangeMap sin respuesta extra."""
    legacy, extended = connection(), connection()
    extended.capabilities.supported = Capability.SKILLS_CATALOG
    baseline = build_logged_response(1) + build_change_map_response(1)
    for peer in [legacy, extended]:
        peer.mark_authenticated()
        await peer.send(baseline)
    await TaskCapabilities(b"\xfa\x01\xff\x00\x00\x00", MagicMock(connection=extended)).execute()
    for peer in [legacy, extended]:
        await peer.flush()
    assert b"".join(call.args[0] for call in legacy.writer.write.call_args_list) == baseline
    assert b"".join(
        call.args[0] for call in extended.writer.write.call_args_list
    ) == baseline + struct.pack("<BBi", 250, 1, 1)
    assert legacy.capabilities.enabled == 0
    assert extended.capabilities.enabled == 1
    for peer in [legacy, extended]:
        peer.close()
        await peer.wait_closed()
        assert peer.capabilities.enabled == 0
    replacement = connection()
    assert replacement.capabilities.enabled == 0
    replacement.close()
    await replacement.wait_closed()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("authenticated", "version", "requested"), [(False, 1, 255), (True, 2, 255), (True, 1, -1)]
)
async def test_invalid_negotiation_never_emits_or_changes_login(
    authenticated, version, requested
) -> None:
    """No se envían capacidades espontáneas ni se altera la autenticación existente."""
    peer = connection()
    if authenticated:
        peer.mark_authenticated()
    await TaskCapabilities(
        struct.pack("<BBi", 250, version, requested), MagicMock(connection=peer)
    ).execute()
    await peer.flush()
    peer.writer.write.assert_not_called()
    assert peer.is_authenticated == authenticated
    assert peer.capabilities.enabled == 0
    peer.close()
    await peer.wait_closed()
