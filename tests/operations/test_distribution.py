"""Regresiones de nombres instalables y colisiones entre artefactos por OS."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from src.operations.distribution import assemble, distribution_identity


def _artifact(directory: Path, platform: str, payload: bytes) -> Path:
    folder = directory / platform
    folder.mkdir()
    files = []
    for name in ("pyao_server-1.0.0-py3-none-any.whl", "pyao_server-1.0.0.tar.gz"):
        (folder / name).write_bytes(payload)
        files.append({"name": name, "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = folder / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "platform": platform,
                "project": "pyao-server",
                "version": "1.0.0",
                "verified_install": True,
                "files": files,
            }
        )
    )
    return manifest


@pytest.mark.parametrize(
    "name",
    [
        "pyao_server-1.0.0-py3-none-any-ubuntu-latest.whl",
        "pyao_server-1.0.0-ubuntu-latest.tar.gz",
        "another_project-1.0.0-py3-none-any.whl",
    ],
)
def test_invalid_renamed_distribution_rejected(name: str) -> None:
    """Un sufijo de OS no convierte el nombre del backend en un artefacto válido."""
    with pytest.raises(ValueError, match=r".+"):
        distribution_identity(Path(name))


def test_platform_containers_keep_original_filenames_and_distinct_content(tmp_path: Path) -> None:
    """Las distribuciones homónimas de Windows y Linux nunca se sobreescriben."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    _artifact(incoming, "ubuntu-24.04", b"linux")
    _artifact(incoming, "windows-latest", b"windows")
    output = tmp_path / "output"
    assemble(incoming, output, "ubuntu-24.04")
    name = "pyao_server-1.0.0-py3-none-any.whl"
    assert (output / name).read_bytes() == b"linux"
    with zipfile.ZipFile(output / "pyao-server-1.0.0-windows-latest.zip") as archive:
        assert archive.read(name) == b"windows"
    assert name in (output / "SHA256SUMS").read_text()
    with pytest.raises(ValueError, match="sobreescriben"):
        assemble(incoming, output, "ubuntu-24.04")


@pytest.mark.parametrize("invalid", ["hash", "unverified", "missing_sdist", "other_version"])
def test_invalid_manifest_cannot_produce_release(tmp_path: Path, invalid: str) -> None:
    """Un paquete alterado o incompleto impide ensamblar cualquier asset."""
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    manifest = _artifact(incoming, "ubuntu-24.04", b"linux")
    record = json.loads(manifest.read_text())
    if invalid == "hash":
        (manifest.parent / record["files"][0]["name"]).write_bytes(b"changed")
    elif invalid == "unverified":
        record["verified_install"] = False
    elif invalid == "missing_sdist":
        record["files"] = record["files"][:1]
    else:
        record["version"] = "2.0.0"
    manifest.write_text(json.dumps(record))
    output = tmp_path / "output"
    with pytest.raises(ValueError, match=r".+"):
        assemble(incoming, output, "ubuntu-24.04")
    assert not output.exists()
