"""Validación contractual exhaustiva con bytes conocidos y escritores reales."""

import importlib
import json
import math
import operator
import struct
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.models.clan import Clan
from src.models.skills import CATALOG, SkillProgress
from src.network.capabilities import CAPABILITIES_VERSION, NEGOTIATION_WINDOW_SECONDS, Capability
from src.network.packet_framer import CONTRACT, FramingError, PacketFramer, validate_packet
from src.network.packet_id import ClientPacketID
from src.server import ArgentumServer

FIXTURES = json.loads(
    (Path(__file__).parents[2] / "src/network/protocol/fixtures.json").read_text()
)
FORMATS = {"u8": "B", "i16": "h", "i32": "i", "u32": "I", "f32": "f"}


def test_capability_metadata_matches_implemented_constants():
    """La ventana de negociación de 30 segundos no cambia el presupuesto de login."""
    metadata = CONTRACT["capabilities"]
    assert metadata["version"] == CAPABILITIES_VERSION
    assert metadata["request_window_server_seconds"] == NEGOTIATION_WINDOW_SECONDS
    assert metadata["response_timeout_client_seconds"] == 30
    assert metadata["login_budget_seconds"] == 5
    assert metadata["mask_bits"] == {bit.name.lower(): int(bit) for bit in Capability}
    for packet_id in (9, 10, 84, 85, 99):
        assert CONTRACT["directions"]["server"][str(packet_id)]["status"] == "unsupported"
    for packet_id in (18, 19, 22, 23, 48):
        assert CONTRACT["directions"]["client"][str(packet_id)]["status"] == "unsupported"


def test_every_supported_packet_and_variant_has_known_bytes():
    """Ni un enum ni un writer sin receptor cuentan como cobertura."""
    for side, entries in CONTRACT["directions"].items():
        for packet_id, entry in entries.items():
            if entry["status"] != "supported":
                continue
            samples = [
                bytes.fromhex(fixture["hex"])
                for fixture in FIXTURES
                if fixture["direction"] == side and int(fixture["hex"][:2], 16) == int(packet_id)
            ]
            assert samples, (side, packet_id)
            for variant in entry.get("variants", {}):
                assert any(sample[1] == int(variant) for sample in samples)


@pytest.mark.parametrize("fixture", FIXTURES, ids=operator.itemgetter("name"))
def test_real_python_writer_matches_independent_golden(fixture):
    """Los constructores reales no se verifican leyendo sólo su propio resultado."""
    if "python" not in fixture:
        return
    writer = fixture["python"]
    kwargs = writer["kwargs"].copy()
    if "clan" in kwargs:
        kwargs["clan"] = Clan(**kwargs["clan"])
    if "progress" in kwargs:
        kwargs = {
            "progress": [SkillProgress(definition, 3, 0, 4) for definition in CATALOG],
            "free_points": 5,
        }
    function = getattr(importlib.import_module(writer["module"]), writer["function"])
    assert function(**kwargs) == bytes.fromhex(fixture["hex"])


@pytest.mark.parametrize("fixture", FIXTURES, ids=operator.itemgetter("name"))
def test_both_directions_every_fragment_boundary_and_coalesced_tail(fixture):
    """Un fragmento válido se acumula y nunca consume el mensaje siguiente."""
    data = bytes.fromhex(fixture["hex"])
    direction = fixture["direction"]
    validate_packet(data, direction)
    tail = bytes([119 if direction == "client" else 88])
    for split in range(1, len(data)):
        framer = PacketFramer(direction)
        framer.feed(data[:split])
        assert framer.next_packet() is None
        framer.feed(data[split:] + tail)
        assert framer.next_packet() == data
        assert framer.next_packet() == tail
        assert framer.buffer_size == 0
    with pytest.raises(FramingError):
        validate_packet(data + tail, direction)
    with pytest.raises(FramingError):
        validate_packet(data[:-1], direction)


@pytest.mark.parametrize("fixture", FIXTURES, ids=operator.itemgetter("name"))
def test_numeric_bounds_and_nonfinite_are_rejected_before_dispatch(fixture):
    """Ensaya los límites de cada campo numérico que declara el contrato."""
    data = bytes.fromhex(fixture["hex"])
    entry = CONTRACT["directions"][fixture["direction"]][str(data[0])]
    fields = entry["fields"] + entry.get("variants", {}).get(
        str(data[1]) if len(data) > 1 else "", []
    )
    offset = 1
    for field in fields:
        if field["type"] == "str16":
            offset += 2 + int.from_bytes(data[offset : offset + 2], "little")
            continue
        fmt = "<" + FORMATS[field["type"]]
        candidates = [field["min"] - 1] if "min" in field else []
        if "max" in field:
            candidates.append(field["max"] + 1)
        if field["type"] == "f32":
            candidates.extend([math.nan, math.inf, -math.inf])
        for value in candidates:
            try:
                replacement = struct.pack(fmt, value)
            except struct.error:
                continue
            changed = data[:offset] + replacement + data[offset + struct.calcsize(fmt) :]
            with pytest.raises(FramingError):
                validate_packet(changed, fixture["direction"])
        offset += struct.calcsize(fmt)


def test_authenticated_state_and_extension_gates():
    """Un opcode correcto no habilita sesión ni capacidad por sí solo."""
    server = ArgentumServer.__new__(ArgentumServer)
    connection = SimpleNamespace(
        is_authenticated=False, capabilities=SimpleNamespace(enabled=Capability.NONE)
    )
    server._validate_packet_state(bytes([ClientPacketID.PING]), connection)
    with pytest.raises(FramingError):
        server._validate_packet_state(bytes([ClientPacketID.ATTACK]), connection)
    connection.is_authenticated = True
    for packet_id in (
        ClientPacketID.LOGIN,
        ClientPacketID.CREATE_ACCOUNT,
        ClientPacketID.TRADE_ACTION,
    ):
        with pytest.raises(FramingError):
            server._validate_packet_state(bytes([packet_id]), connection)
    connection.capabilities.enabled = Capability.TRADE_STATE
    server._validate_packet_state(bytes([ClientPacketID.TRADE_ACTION]), connection)
