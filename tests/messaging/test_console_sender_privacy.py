"""La consola conserva el contenido del protocolo sin copiarlo a los logs."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_console_sender import ConsoleMessageSender
from src.network.packet_id import ServerPacketID


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["console", "multiline", "error"])
async def test_console_payload_is_delivered_but_never_logged(caplog, operation: str) -> None:
    """Un canario libre, sin etiqueta password, tampoco se filtra en bytes hex."""
    connection = MagicMock()
    connection.address = ("127.0.0.1", 12345)
    connection.send = AsyncMock()
    sender = ConsoleMessageSender(connection)
    secret = "SYNTHETIC_PRIVATE_CONTENT_482"
    caplog.set_level(logging.DEBUG)

    if operation == "error":
        await sender.send_error_msg(secret)
        opcode, color, lines = ServerPacketID.ERROR_MSG, b"", [secret]
    elif operation == "multiline":
        await sender.send_multiline_console_msg(secret + "\n \n" + secret + "_2", 3)
        opcode, color, lines = ServerPacketID.CONSOLE_MSG, b"\x03", [secret, secret + "_2"]
    else:
        await sender.send_console_msg(secret, 3)
        opcode, color, lines = ServerPacketID.CONSOLE_MSG, b"\x03", [secret]

    expected = []
    for line in lines:
        payload = line.encode("latin-1")
        expected.append(
            bytes([opcode]) + len(payload).to_bytes(2, "little", signed=True) + payload + color
        )
    assert [call.args[0] for call in connection.send.await_args_list] == expected
    assert "Enviando" in caplog.text
    for line in lines:
        assert line not in caplog.text
        assert line.encode().hex() not in caplog.text
