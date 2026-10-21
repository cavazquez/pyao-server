"""Contratos de las utilidades conservadas tras completar el tipado."""

import json
import signal
import subprocess  # ruff: ignore[suspicious-subprocess-import] - Sólo se intercepta en estas regresiones.
import tomllib
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts import analyze_redundant_tests as coverage_analysis
from scripts import check_class_skills, find_real_redundant_tests
from scripts.fix_toml_format import fix_npcs_toml
from scripts.regenerate_npcs_toml import generate_toml, parse_npcs_dat
from scripts.smoke_installed_snap import signal_snap
from scripts.sync_merchant_inventories import generate_toml_content, load_merchants_from_file


def test_npc_regeneration_preserves_appearance_combat_sounds_and_stock(tmp_path: Path) -> None:
    """La entrada VB6 temporal produce TOML válido con sus campos opcionales."""
    source = tmp_path / "NPCs.dat"
    source.write_text(
        "[NPC7]\nName=Herrero\nDesc=Espadas y escudos\nComercia=1\nHostile=0\n"
        "Head=3\nBody=1\nHeading=2\nSnd1=18\nsnd2=19\nMaxHP=100\nMinHP=50\n"
        "MaxHit=10\nMinHit=3\nNROITEMS=1\nObj1=15-8\n",
        encoding="latin-1",
    )
    rows = parse_npcs_dat(source)
    rendered = tomllib.loads(generate_toml(rows, "npcs_complete"))["npcs_complete"]["npcs"]
    assert len(rendered) == 1
    assert rendered[0]["appearance"] == {
        "head": 3,
        "body": 1,
        "heading": 2,
        "sounds": [18, 19, 0],
    }
    assert rendered[0]["combat"] == {"max_hp": 100, "min_hp": 50, "max_hit": 10, "min_hit": 3}
    assert rendered[0]["inventory"]["items"] == [{"slot": 1, "item_id": 15, "quantity": 8}]


def test_legacy_merchant_inventory_round_trip_in_temporary_files(tmp_path: Path) -> None:
    """El parser tolerante conserva artículos y cantidades de las fuentes antiguas."""
    source = tmp_path / "npcs.toml"
    source.write_text(
        '[[npcs_complete.npcs]]\nid=7\nname="Herrero"\ntrades=1\n'
        "[inventory]\nitems=[{slot=1,item_id=15,quantity=8}]\n",
        encoding="utf-8",
    )
    rows = load_merchants_from_file(source, source.name)
    rendered = tomllib.loads(generate_toml_content(rows))["merchant"]
    assert rendered[0]["npc_id"] == 7
    assert rendered[0]["item"][0]["item_id"] == 15
    assert rendered[0]["item"][0]["quantity"] == 8
    assert rows[0]["source"] == "npcs.toml"


def test_toml_format_repair_preserves_top_level_and_converts_sections() -> None:
    """Las anotaciones de regex no cambian la transformación de subtablas."""
    source = '[npcs_complete]\nname="Guardia"\n[appearance]\nhead=3\nbody=1\n'
    rendered = tomllib.loads(fix_npcs_toml(source))
    assert rendered["npcs_complete"]["name"] == "Guardia"
    assert rendered["npcs_complete"]["appearance"] == {"head": 3, "body": 1}


def test_coverage_analysis_and_report_use_unique_source_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dos fuentes temporales comparten una línea y conservan sus aportes únicos."""
    lines = {
        "tests/test_a.py": {("src/a.py", 1), ("src/a.py", 2)},
        "tests/test_b.py": {("src/a.py", 2)},
    }
    monkeypatch.setattr(
        coverage_analysis, "get_coverage_for_test_file", lambda name, _root: lines[name]
    )
    result = coverage_analysis.analyze_redundant_tests(list(lines), tmp_path)
    assert result["tests/test_a.py"]["unique_lines"] == {("src/a.py", 1)}
    assert result["tests/test_b.py"]["unique_count"] == 0
    report = tmp_path / "report.md"
    coverage_analysis.generate_report(result, report)
    assert "tests/test_a.py" in report.read_text()
    assert "tests/test_b.py" in report.read_text()


def test_coverage_json_count_and_failed_probe_restore_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un sondeo fallido nunca deja el archivo de prueba renombrado."""
    (tmp_path / "coverage.json").write_text(json.dumps({"totals": {"covered_lines": 12}}))
    monkeypatch.setattr(
        subprocess, "run", lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0)
    )
    assert find_real_redundant_tests.get_coverage_lines(tmp_path) == 12
    source = tmp_path / "test_a.py"
    source.write_text("assert True\n")
    probes = MagicMock(side_effect=[12, RuntimeError("probe failed")])
    monkeypatch.setattr(find_real_redundant_tests, "get_coverage_lines", probes)
    with pytest.raises(RuntimeError, match="probe failed"):
        find_real_redundant_tests.test_remove_single_file(tmp_path, source.name)
    assert source.read_text() == "assert True\n"
    assert not (tmp_path / "test_a.py.backup").exists()


@pytest.mark.asyncio
async def test_skill_diagnostic_uses_current_connection_and_always_closes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El diagnóstico lee habilidades sin sembrar defaults ni dejar Redis conectado."""
    client = MagicMock(connect=AsyncMock(), disconnect=AsyncMock())
    player = MagicMock(get_skills=AsyncMock(return_value={"talar": 12}))
    monkeypatch.setattr(check_class_skills, "RedisClient", lambda: client)
    monkeypatch.setattr(check_class_skills, "PlayerRepository", lambda _client: player)
    await check_class_skills.check_user_skills(7)
    client.connect.assert_awaited_once_with(seed_defaults=False)
    client.disconnect.assert_awaited_once()
    player.get_skills.side_effect = RuntimeError("read failed")
    with pytest.raises(RuntimeError, match="read failed"):
        await check_class_skills.check_user_skills(7)
    assert client.disconnect.await_count == 2


def test_snap_cleanup_from_confined_session_targets_only_its_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """La alternativa AppArmor usa el PID creado por la prueba y argumentos separados."""
    process = MagicMock(pid=12345)
    process.send_signal.side_effect = PermissionError
    run = MagicMock()
    monkeypatch.setattr(subprocess, "run", run)
    signal_snap(process, signal.SIGTERM)
    arguments = run.call_args.args[0]
    assert arguments[:4] == ["snap", "run", "--shell", "pyao.pyao-server"]
    assert arguments[-2:] == ["TERM", "12345"]
    assert run.call_args.kwargs == {"check": True, "timeout": 15}
