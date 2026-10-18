"""El cliente de integración usa los mismos bytes golden que Godot."""

import json
from pathlib import Path

from src.operations.two_client_smoke import login_packet


def test_smoke_login_matches_shared_fixture() -> None:
    """Evita validar servidor y harness con un segundo layout inventado."""
    fixtures = json.loads(
        (Path(__file__).parents[2] / "src/network/protocol/fixtures.json").read_text()
    )
    expected = next(bytes.fromhex(row["hex"]) for row in fixtures if row["name"] == "login_latin1")
    assert login_packet("Peña", "cláve1") == expected
