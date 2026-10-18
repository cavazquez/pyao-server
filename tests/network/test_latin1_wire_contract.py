"""Regresiones contra bytes idénticos a los writers Godot, sin normalizar secretos."""

import json
import operator
import struct
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.commands.base import CommandResult
from src.network.packet_reader import PacketReader
from src.network.validators.base import ValidationContext
from src.network.validators.chat import TalkPacketValidator, WhisperPacketValidator
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_login import TaskLogin
from src.tasks.task_party_join import TaskPartyJoin

FIXTURES = {
    fixture["name"]: bytes.fromhex(fixture["hex"])
    for fixture in json.loads(
        (Path(__file__).parents[2] / "src/network/protocol/fixtures.json").read_text()
    )
}


def wire_string(value: str) -> bytes:
    """Codifica estrictamente el layout de una cadena AO de prueba.

    Returns:
        Prefijo u16 y bytes Latin-1 originales.
    """
    data = value.encode("latin-1")
    return struct.pack("<H", len(data)) + data


def test_auth_tasks_consume_shared_fixtures_with_exact_values() -> None:
    """Una sola capa interpreta auth y la selección completa del personaje."""
    assert TaskLogin(FIXTURES["login_latin1"], MagicMock())._parse_packet() == ("Peña", "cláve1")
    assert TaskCreateAccount(FIXTURES["create_latin1"], MagicMock())._parse_packet() == (
        "Peña",
        "cláve1",
        "test@example.invalid",
        {"race": 1, "gender": 1, "job": 1, "head": 1, "home": 1},
    )
    packet = b"\x00" + wire_string("Señor") + wire_string("  Cláve  ") + b"\x00\x0d\x00"
    assert TaskLogin(packet, MagicMock())._parse_packet() == ("Señor", "  Cláve  ")


def test_chat_preserves_latin1_and_rejects_truncation() -> None:
    """No se decodifica ñ como UTF-8 ni se consume un string anunciado incompleto."""
    talk = TalkPacketValidator().validate(
        ValidationContext(PacketReader(FIXTURES["talk_latin1"]), [])
    )
    assert talk.success
    assert talk.data == {"message": "¡Hola, señor! áéíóú"}
    whisper = b"\x05" + wire_string("Peña") + wire_string("¡Qué tal!")
    result = WhisperPacketValidator().validate(ValidationContext(PacketReader(whisper), []))
    assert result.success
    assert result.data == {"receiver": "Peña", "message": "¡Qué tal!"}
    assert (
        not TalkPacketValidator()
        .validate(ValidationContext(PacketReader(FIXTURES["talk_latin1"][:-1]), []))
        .success
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("nickname", ["Ana", "Peña"])
async def test_party_join_delegates_canonical_nickname_once(nickname: str) -> None:
    """La invitación usa u16/Latin-1 y conserva literalmente el destinatario."""
    handler = MagicMock(handle=AsyncMock(return_value=CommandResult.ok()))
    sender = MagicMock(send_console_msg=AsyncMock())
    packet = b"\x5d" + wire_string(nickname)
    await TaskPartyJoin(packet, sender, handler, {"user_id": 10}).execute()
    handler.handle.assert_awaited_once()
    assert handler.handle.call_args.args[0].target_username == nickname


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload", [b"\x5d", b"\x5d\x00\x00", b"\x5d\x03\x00An", b"\x5d\x15\x00" + b"a" * 21]
)
async def test_party_join_invalid_payload_never_invites(payload: bytes) -> None:
    """La forma antigua, vacía, truncada o demasiado larga no llega al handler."""
    handler = MagicMock(handle=AsyncMock())
    sender = MagicMock(send_console_msg=AsyncMock())
    await TaskPartyJoin(payload, sender, handler, {"user_id": 10}).execute()
    handler.handle.assert_not_called()
    await TaskPartyJoin(FIXTURES["party_join"], sender, handler, {}).execute()
    handler.handle.assert_not_called()


@pytest.mark.parametrize(
    "vector",
    json.loads((Path(__file__).parents[2] / "src/network/protocol/credentials.json").read_text()),
    ids=operator.itemgetter("name"),
)
def test_shared_credential_boundary_vectors(vector: dict) -> None:
    """Login y alta comparten límites por bytes y representación estricta."""
    from src.network.validators.auth import (  # noqa: PLC0415
        CreateAccountPacketValidator,
        LoginPacketValidator,
    )

    try:
        credentials = wire_string(vector["username"]) + wire_string(vector["password"])
    except UnicodeEncodeError:
        assert not vector["accepted"]
        return
    login = b"\x00" + credentials + b"\x00\x0d\x00"
    signup = (
        b"\x02"
        + credentials
        + b"\x00\x0d\x00\x01\x01\x01\x01\x00"
        + wire_string("test@example.invalid")
        + b"\x01"
    )
    for validator, packet in [
        (LoginPacketValidator(), login),
        (CreateAccountPacketValidator(), signup),
    ]:
        result = validator.validate(ValidationContext(PacketReader(packet), []))
        assert result.success == vector["accepted"]
        if result.success:
            assert result.data["username"] == vector["username"]
            assert result.data["password"] == vector["password"]
