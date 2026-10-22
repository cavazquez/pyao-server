"""Paquetes de canales: identidad común y rechazo de candidatos alterados."""

import json
import shutil
import subprocess  # noqa: S404 - Comandos dpkg fijos sobre paquetes de fixture propios.
import zipfile
from pathlib import Path

import pytest

from tools.channel_repository import (
    prepare,
    read_artifact,
    read_winget_manifest,
    verify_installation_checks,
    write_recipes,
)
from tools.package_channels import (
    archive_tree,
    build_deb,
    deb_asset_name,
    deb_version,
    file_inventory,
    seal_server,
    sha,
    verify_inventory,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1.0.0rc5", "1.0.0~rc5"), ("1.0.0", "1.0.0"), ("1.2.0rc12", "1.2.0~rc12")],
)
def test_debian_version_preserves_prerelease_order(value: str, expected: str) -> None:
    """La sintaxis Debian conserva la identidad de producto y ordena RC antes de final."""
    assert deb_version(value) == expected


@pytest.mark.parametrize(
    ("archive", "expected"),
    [
        ("pyao-server_1.0.0~rc5_amd64.deb", "pyao-server_1.0.0.rc5_amd64.deb"),
        ("pyao-client_1.0.0~rc5_arm64.deb", "pyao-client_1.0.0.rc5_arm64.deb"),
        ("pyao-client_1.0.0_amd64.deb", "pyao-client_1.0.0_amd64.deb"),
    ],
)
def test_debian_asset_name_survives_github_normalization(archive: str, expected: str) -> None:
    """GitHub sustituye el tilde; el índice debe usar el mismo nombre público."""
    assert deb_asset_name(archive) == expected
    assert deb_asset_name(expected) == expected


@pytest.mark.parametrize("archive", ["../app.deb", "a/b.deb", "a\\b.deb", "x y.deb", "x.zip"])
def test_debian_asset_name_rejects_escaping_or_ambiguous_paths(archive: str) -> None:
    """Un nombre remoto no puede introducir rutas ni caracteres normalizados."""
    with pytest.raises(ValueError, match="Debian"):
        deb_asset_name(archive)


@pytest.mark.parametrize("platform_name", ["linux", "linux-arm64"])
def test_debian_rc_keeps_internal_order_and_runtime_bytes(
    tmp_path: Path, platform_name: str
) -> None:
    """Construye un .deb de fixture y comprueba su control y payload reales."""
    dpkg_deb = shutil.which("dpkg-deb")
    dpkg = shutil.which("dpkg")
    if dpkg_deb is None or dpkg is None:
        pytest.skip("La fixture requiere las herramientas Debian")
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    executable = "pyao-client.arm64" if platform_name.endswith("arm64") else "pyao-client.x86_64"
    payload = b"#!/bin/sh\nexit 0\n"
    (candidate / executable).write_bytes(payload)
    (candidate / executable).chmod(0o755)
    (candidate / "pyao-client.png").write_bytes(b"unit-fixture-icon")
    (candidate / "LICENSE").write_text("unit fixture")
    record = {
        "platform": platform_name,
        "version": "1.0.0rc5",
        "commit": "a" * 40,
        "dirty": False,
        "files": file_inventory(candidate),
        "user_data_name": "unit-fixture",
    }
    manifest = candidate / "candidate-manifest.json"
    manifest.write_text(json.dumps(record))
    proof = tmp_path / "proof.json"
    proof.write_text(json.dumps({"passed": True, "candidate_manifest_sha256": sha(manifest)}))
    result = build_deb(candidate, "client", proof, tmp_path / "debs")
    package = tmp_path / "debs" / result["archive"]
    assert "~" not in package.name
    assert ".rc5_" in package.name
    version = subprocess.check_output(  # noqa: S603 - Lector dpkg sobre el paquete de esta fixture.
        [dpkg_deb, "--field", str(package), "Version"], text=True
    )
    assert version.strip() == "1.0.0~rc5"
    subprocess.run(  # noqa: S603 - Comparación de versiones generadas por la fixture.
        [dpkg, "--compare-versions", version.strip(), "lt", "1.0.0"], check=True
    )
    extracted = tmp_path / "extracted"
    subprocess.run(  # noqa: S603 - Extracción del paquete propio dentro de tmp_path.
        [dpkg_deb, "--extract", str(package), str(extracted)], check=True
    )
    assert (extracted / "opt/pyao-client" / executable).read_bytes() == payload


@pytest.mark.parametrize("value", ["../1", "1.0.0; x", "v1.0.0", "1.0.0rc-1"])
def test_invalid_product_version_cannot_enter_package_paths(value: str) -> None:
    """Ninguna versión arbitraria se interpola en nombres de archivos o recetas."""
    with pytest.raises(ValueError, match="Versión"):
        deb_version(value)


def test_inventory_detects_extra_changed_and_escaping_files(tmp_path: Path) -> None:
    """Se compara el árbol completo y los enlaces permanecen dentro del candidato."""
    (tmp_path / "app").write_bytes(b"approved")
    expected = file_inventory(tmp_path)
    verify_inventory(tmp_path, expected)
    (tmp_path / "extra").write_bytes(b"unexpected")
    with pytest.raises(ValueError, match="cambió"):
        verify_inventory(tmp_path, expected)
    (tmp_path / "extra").unlink()
    (tmp_path / "app").write_bytes(b"changed")
    with pytest.raises(ValueError, match="cambió"):
        verify_inventory(tmp_path, expected)
    (tmp_path / "outside").symlink_to(tmp_path.parent)
    with pytest.raises(ValueError, match="Enlace fuera"):
        file_inventory(tmp_path)


def test_zip_preserves_runtime_symlinks_and_executable_mode(tmp_path: Path) -> None:
    """El Python privado conserva sus enlaces relativos y permisos al archivarse."""
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "python3.14").write_bytes(b"interpreter")
    (source / "python3.14").chmod(0o755)
    (source / "python3").symlink_to("python3.14")
    archive_tree(source, tmp_path / "payload.zip")
    with zipfile.ZipFile(tmp_path / "payload.zip") as archive:
        assert archive.read("python3") == b"python3.14"
        assert (archive.getinfo("python3").external_attr >> 16) & 0o170000 == 0o120000
        assert (archive.getinfo("python3.14").external_attr >> 16) & 0o111 == 0o111


@pytest.mark.parametrize("payload", [b"", b"\n", b"uv", b"uv\n"])
def test_zip_metadata_never_expands_into_a_dangerous_negative_compression_ratio(
    tmp_path: Path, payload: bytes
) -> None:
    """Conserva metadatos mínimos sin el rechazo estructural de WinGet (#396)."""
    source = tmp_path / "candidate"
    source.mkdir()
    (source / "INSTALLER").write_bytes(payload)
    archive_tree(source, tmp_path / "payload.zip")
    with zipfile.ZipFile(tmp_path / "payload.zip") as archive:
        info = archive.getinfo("INSTALLER")
        assert archive.read(info) == payload
        assert info.compress_size <= info.file_size


def test_server_cannot_be_sealed_with_another_pair_or_changed_payload(tmp_path: Path) -> None:
    """Un PONG aislado o una prueba de otro servidor no habilitan publicación."""
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    (candidate / "app").write_bytes(b"server")
    record = {
        "version": "1.0.0rc5",
        "commit": "a" * 40,
        "dirty": False,
        "platform": "linux-amd64",
        "files": file_inventory(candidate),
    }
    manifest = candidate / "server-candidate.json"
    manifest.write_text(json.dumps(record))
    cli = tmp_path / "cli.json"
    cli.write_text(json.dumps({"passed": True, "candidate_manifest_sha256": sha(manifest)}))
    pair = tmp_path / "pair.json"
    pair.write_text(
        json.dumps(
            {
                "regression_passed": True,
                "tls": True,
                "installed_wheel": True,
                "server_commit": "b" * 40,
                "release_version": "1.0.0rc5",
                "server_candidate_sha256": sha(manifest),
            }
        )
    )
    with pytest.raises(ValueError, match="mismo servidor"):
        seal_server(candidate, cli, pair, tmp_path / "output")
    proof = json.loads(pair.read_text())
    proof.update(server_commit="a" * 40, client_commit="c" * 40)
    pair.write_text(json.dumps(proof))
    (candidate / "app").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="cambió"):
        seal_server(candidate, cli, pair, tmp_path / "output")


def test_channels_reject_unverified_or_modified_artifact(tmp_path: Path) -> None:
    """Las recetas sólo referencian bytes aprobados de la misma versión y commit."""
    archive = tmp_path / "client.zip"
    archive.write_bytes(b"approved")
    record = {
        "version": "1.0.0rc5",
        "commit": "a" * 40,
        "archive": archive.name,
        "sha256": sha(archive),
        "verified": True,
    }
    path = tmp_path / "client.json"
    path.write_text(json.dumps(record))
    assert read_artifact(path, "1.0.0rc5", "a" * 40)["path"] == archive
    archive.write_bytes(b"changed")
    with pytest.raises(ValueError, match="cambiado"):
        read_artifact(path, "1.0.0rc5", "a" * 40)
    record["verified"] = False
    path.write_text(json.dumps(record))
    with pytest.raises(ValueError, match="sin validación"):
        read_artifact(path, "1.0.0rc5", "a" * 40)


def test_brew_and_winget_recipes_use_immutable_pair_urls_and_correct_licenses(
    tmp_path: Path,
) -> None:
    """La versión común no mezcla licencias ni enlaces a latest o a otro candidato."""
    records = {role: {} for role in ("server", "client")}
    for role, targets in records.items():
        for target in ("macos-arm64", "macos-amd64", "windows-amd64"):
            suffix = target.replace("amd64", "x86_64") if role == "client" else target
            targets[target] = {
                "archive": f"pyao-{role}-1.0.0rc5-{suffix}.zip",
                "sha256": "a" * 64,
                "files": {"pyao-client.app/Contents/MacOS/pyao-client": "b" * 64},
            }
    write_recipes(tmp_path, records, "1.0.0rc5")
    formula = (tmp_path / "Formula/pyao-server.rb").read_text()
    assert 'license "Apache-2.0"' in formula
    assert "/releases/download/v1.0.0rc5/" in formula
    assert "latest" not in formula
    assert "Redis es externo" in formula
    assert 'app "pyao-client.app"' in (tmp_path / "Casks/pyao-client.rb").read_text()
    for role, identifier, license_name in (
        ("server", "Cavazquez.PyAOServer", "Apache-2.0"),
        ("client", "Cavazquez.PyAOClient", "MIT"),
    ):
        folder = tmp_path / "winget" / identifier / "1.0.0rc5"
        for path in folder.glob("*.yaml"):
            manifest = read_winget_manifest(path)
            assert path.read_text().splitlines()[0] == (
                "# yaml-language-server: $schema=https://aka.ms/winget-manifest."
                f"{manifest['ManifestType']}.{manifest['ManifestVersion']}.schema.json"
            )
        locale = read_winget_manifest(folder / f"{identifier}.locale.es-AR.yaml")
        installer = read_winget_manifest(folder / f"{identifier}.installer.yaml")
        assert locale["License"] == license_name
        assert installer["PackageVersion"] == "1.0.0rc5"
        assert (
            installer["Installers"][0]["NestedInstallerFiles"][0]["PortableCommandAlias"]
            == "pyao-" + role
        )


def test_channel_repository_requires_every_native_installation_proof(tmp_path: Path) -> None:
    """Un conjunto de ZIPs correcto todavía no acredita instalaciones del par."""
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "version": "1.0.0rc5",
                "sources": {"server": "a" * 40, "client": "b" * 40},
                "checks": [],
            }
        )
    )
    with pytest.raises(ValueError, match="cinco pruebas"):
        prepare(plan, tmp_path / "channel")
    assert not (tmp_path / "channel").exists()


def test_installation_proof_from_another_pair_cannot_promote_recipes(tmp_path: Path) -> None:
    """La aceptación de instaladores se vincula a ambos commits del producto."""
    proof = tmp_path / "proof.json"
    proof.write_text(
        json.dumps(
            {
                "channel": "winget",
                "platform": "windows-amd64",
                "sources": {"server": "c" * 40, "client": "b" * 40},
                "version": "1.0.0rc5",
            }
        )
    )
    plan = {
        "version": "1.0.0rc5",
        "sources": {"server": "a" * 40, "client": "b" * 40},
        "checks": [proof.name],
    }
    with pytest.raises(ValueError, match="otro par"):
        verify_installation_checks(plan, tmp_path, {}, [])
