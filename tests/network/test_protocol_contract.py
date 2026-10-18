"""Fixtures binarias compartidas: bytes conocidos y límites del contrato pyao."""

import json
import operator
import struct
from pathlib import Path

import pytest

from src.network.packet_handlers import TASK_HANDLERS
from src.network.packet_id import ClientPacketID, ServerPacketID

PROTOCOL = Path(__file__).parents[2] / "src/network/protocol"
CONTRACT = json.loads((PROTOCOL / "contract.json").read_text())
FIXTURES = json.loads((PROTOCOL / "fixtures.json").read_text())


def test_supported_handlers_and_enum_ids_are_explicit() -> None:
    """Cada handler real tiene campos; enumerar un ID no lo habilita."""
    for direction, enum in [("client", ClientPacketID), ("server", ServerPacketID)]:
        entries = CONTRACT["directions"][direction]
        assert all(str(packet) in entries for packet in enum)
        assert all(entry["status"] in {"supported", "unsupported"} for entry in entries.values())
    supported = {
        int(key)
        for key, entry in CONTRACT["directions"]["client"].items()
        if entry["status"] == "supported"
    }
    assert supported == set(TASK_HANDLERS)
    assert CONTRACT["inventory_slots"] == 30
    assert CONTRACT["string_encoding"] == "iso-8859-1"


@pytest.mark.parametrize("fixture", FIXTURES, ids=operator.itemgetter("name"))
def test_golden_fields_consume_exactly_the_packet(fixture: dict) -> None:
    """Decodifica bytes fijos sin invocar writers que puedan repetir el mismo error."""
    data = bytes.fromhex(fixture["hex"])
    entry = CONTRACT["directions"][fixture["direction"]][str(data[0])]
    offset = 1
    decoded = {}
    for field in entry["fields"]:
        kind = field["type"]
        if kind == "str16":
            length = struct.unpack_from("<H", data, offset)[0]
            offset += 2
            assert length <= field["max_bytes"]
            value = data[offset : offset + length].decode("latin-1")
            offset += length
        else:
            fmt = {"u8": "B", "i16": "h", "i32": "i", "f32": "f"}[kind]
            value = struct.unpack_from("<" + fmt, data, offset)[0]
            offset += struct.calcsize(fmt)
        decoded[field["name"]] = value
    assert offset == len(data)
    expected = dict(fixture["values"])
    if "version" in expected and fixture["direction"] == "client":
        expected.update(zip(["major", "minor", "patch"], expected.pop("version"), strict=True))
    for name, value in expected.items():
        assert decoded[name] == value


def test_critical_legacy_widths_are_preserved() -> None:
    """Logged=0, ChangeMap=5, MoveItem=3 y contadores de clan mayores a int16."""
    fixtures = {entry["name"]: bytes.fromhex(entry["hex"]) for entry in FIXTURES}
    assert fixtures["logged"] == b"\x00\x01"
    assert fixtures["change_map"] == b"\x15\x01\x00\x00\x00"
    assert fixtures["move_item"] == b"\x81\x19\x1e"
    assert fixtures["party_join"] == b"\x5d\x03\x00Ana"
    assert fixtures["double_click"] == b"\x1b\x32\x33"
