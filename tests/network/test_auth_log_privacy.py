"""Los diagnósticos de red no revelan secretos, incluso con paquetes fragmentados."""

import logging
import struct
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.network.client_connection import ClientConnection
from src.network.packet_reader import PacketReader
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_login import TaskLogin
from src.tasks.task_null import TaskNull


@pytest.mark.asyncio
@pytest.mark.parametrize("level", [logging.INFO, logging.DEBUG])
async def test_auth_and_unknown_fragments_never_log_passwords(caplog, level):
    """El mismo secreto atraviesa TCP, alta/login y lectores sin quedar en logs."""
    caplog.set_level(level)
    secret = "CANARY_89_ñ_Secret"
    secret_utf8 = secret.encode("utf-8")
    secret_latin1 = secret.encode("latin-1")
    password_hash = "$argon2id$v=19$m=65536,t=3,p=4$SyntheticHash89"

    def field(value: bytes) -> bytes:
        return struct.pack("<H", len(value)) + value

    sender = MagicMock()
    sender.address = ("127.0.0.1", 12345)
    sender.send_error_msg = AsyncMock()
    handler = MagicMock()
    handler.handle = AsyncMock(return_value=MagicMock(success=True))
    account = (
        b"\x01"
        + field(b"SyntheticUser")
        + field(secret_utf8)
        + b"\x00\x0d\x00\x01\x01\x01\x01\x00"
        + field(b"synthetic@example.invalid")
        + b"\x01"
    )
    await TaskCreateAccount(account, sender, handler).execute()
    await TaskLogin(
        b"\x00" + field(b"SyntheticUser") + field(secret_utf8), sender, handler
    ).execute()
    assert handler.handle.await_count == 2
    # Un stream puede cortar justo antes del password y enviarlo como próximo read.
    writer = MagicMock()
    writer.get_extra_info.return_value = sender.address
    writer.drain = AsyncMock()
    writer.wait_closed = AsyncMock()
    reader = MagicMock()
    reader.read = AsyncMock(side_effect=[account[:6], secret_latin1, secret_utf8])
    connection = ClientConnection(reader, writer)
    for _ in range(3):
        fragment = await connection.receive()
        await TaskNull(fragment, sender).execute()
    await connection.send(password_hash.encode())
    await connection.flush()
    connection.close()
    await connection.wait_closed()
    for encoding, method in [("utf-16-le", "read_string"), ("latin-1", "read_ascii_string")]:
        packet = PacketReader(b"\x00" + field(secret.encode(encoding)))
        assert getattr(packet, method)() == secret
    packet = PacketReader(b"\x00" + struct.pack("<i", len(secret_utf8)) + secret_utf8)
    assert packet.read_godot_put_string() == secret
    for value in [secret, password_hash]:
        assert value not in caplog.text
        for encoding in ["utf-8", "latin-1", "utf-16-le"]:
            for separator in [None, " "]:
                encoded = value.encode(encoding)
                representation = encoded.hex() if separator is None else encoded.hex(separator)
                assert representation.lower() not in caplog.text.lower()
    assert "bytes" in caplog.text
