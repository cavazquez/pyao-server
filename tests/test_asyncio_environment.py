"""Regresión del diagnóstico previo para entornos que bloquean asyncio."""

import errno
import socket
from unittest.mock import MagicMock

import pytest

from tests.conftest import pytest_sessionstart


def test_asyncio_local_channel_available() -> None:
    """Verifica el canal real que asyncio usa para recibir avisos entre hilos."""
    pytest_sessionstart()


@pytest.mark.parametrize(
    ("operation", "error"),
    [
        ("create", PermissionError(errno.EPERM, "socketpair bloqueado")),
        ("send", PermissionError(errno.EPERM, "envío bloqueado")),
        ("receive", TimeoutError("no llegó la señal")),
        ("eof", None),
    ],
)
def test_asyncio_local_channel_failure_is_diagnostic(
    monkeypatch: pytest.MonkeyPatch, operation: str, error: OSError | None
) -> None:
    """Un fallo del canal aborta con diagnóstico y cierra los sockets creados."""
    reader = MagicMock(spec=socket.socket)
    writer = MagicMock(spec=socket.socket)
    reader.__enter__.return_value = reader
    writer.__enter__.return_value = writer
    reader.recv.return_value = b"\x00"
    pair = MagicMock(return_value=(reader, writer))
    monkeypatch.setattr("tests.conftest.socket.socketpair", pair)

    if operation == "create":
        pair.side_effect = error
    elif operation == "send":
        writer.sendall.side_effect = error
    elif operation == "receive":
        reader.recv.side_effect = error
    else:
        reader.recv.return_value = b""

    with pytest.raises(pytest.UsageError, match=r"canal local de asyncio \(socketpair\)"):
        pytest_sessionstart()

    if operation != "create":
        reader.__exit__.assert_called_once()
        writer.__exit__.assert_called_once()
        reader.settimeout.assert_called_once_with(1)
        writer.settimeout.assert_called_once_with(1)
