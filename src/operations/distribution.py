"""Valida distribuciones instaladas y ensambla releases sin renombrar wheels o sdists."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess  # noqa: S404 - comandos uv de la herramienta de release, sin shell.
import sys
import tarfile
import zipfile
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from packaging.utils import canonicalize_name, parse_sdist_filename, parse_wheel_filename

PROJECT = "pyao-server"
ROOT = Path(__file__).resolve().parents[2]
PLATFORM_PATTERN = re.compile(r"^[a-zA-Z0-9_.-]+$")
PROBE = """import importlib.metadata as m, json, pathlib, sys
expected = sys.argv[1]
d = m.distribution("pyao-server")
assert d.version == expected
assert d.metadata["Name"].replace("_", "-").lower() == "pyao-server"
entries = [e for e in d.entry_points if e.group == "console_scripts" and e.name == "pyao-server"]
assert len(entries) == 1 and entries[0].value == "src.run_server:main"
assert callable(entries[0].load())
import src
assert pathlib.Path(src.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
print(json.dumps({"version": d.version, "entry_point": entries[0].value, "isolated": True}))
"""


def _run(
    arguments: list[str],
    *,
    cwd: Path,
    environment: dict[str, str] | None = None,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - argv construido aquí; nunca se invoca un shell.
        arguments,
        cwd=cwd,
        env=environment,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        check=True,
    )


def _sha(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def distribution_identity(path: Path) -> tuple[str, str]:
    """Exige el formato normalizado del backend, sin sufijos de OS agregados.

    Returns:
        Nombre normalizado y versión PEP 440.

    Raises:
        ValueError: Si el nombre no representa un wheel/sdist de PyAO.
    """
    if path.name.endswith(".whl"):
        name, version, _, _ = parse_wheel_filename(path.name)
    else:
        name, version = parse_sdist_filename(path.name)
    if canonicalize_name(name) != PROJECT:
        message = "Distribución de otro proyecto"
        raise ValueError(message)
    return str(name), str(version)


def validate(directory: Path, platform: str, *, project_root: Path = ROOT) -> dict[str, Any]:  # noqa: PLR0914
    """Instala runtime fijado y wheel sin deps en un venv nuevo fuera del checkout.

    Returns:
        Manifiesto de los únicos artefactos que pueden incorporarse a la release.

    Raises:
        ValueError: Ante archivos ausentes, nombres inválidos o versiones distintas.
        RuntimeError: Si uv no está disponible.
    """
    if not PLATFORM_PATTERN.fullmatch(platform):
        message = "Identificador de plataforma inválido"
        raise ValueError(message)
    wheels, sources = list(directory.glob("*.whl")), list(directory.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sources) != 1:
        message = "Se requiere exactamente un wheel y un sdist del backend"
        raise ValueError(message)
    wheel, source = wheels[0].resolve(), sources[0].resolve()
    identity = distribution_identity(wheel)
    if distribution_identity(source) != identity:
        message = "Wheel y sdist no representan la misma versión"
        raise ValueError(message)
    # Leer metadata sin extraer archivos de los archives al sistema.
    with zipfile.ZipFile(wheel) as archive:
        metadata = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if (
            len(metadata) != 1
            or f"Version: {identity[1]}" not in archive.read(metadata[0]).decode()
        ):
            message = "Metadata del wheel no coincide con su nombre"
            raise ValueError(message)
    with tarfile.open(source) as archive:
        source_metadata = [
            member
            for member in archive.getmembers()
            if member.name.count("/") == 1 and member.name.endswith("/PKG-INFO")
        ]
        content = archive.extractfile(source_metadata[0]) if len(source_metadata) == 1 else None
        if content is None or f"Version: {identity[1]}" not in content.read().decode():
            message = "Metadata del sdist no coincide con su nombre"
            raise ValueError(message)
    uv = shutil.which("uv")
    if uv is None:
        message = "Se requiere uv para verificar la instalación"
        raise RuntimeError(message)
    runtime_lock = _run(
        [uv, "export", "--locked", "--no-dev", "--no-emit-project"], cwd=project_root
    ).stdout
    environment = {
        key: value for key, value in os.environ.items() if not key.startswith(("PYAO_", "SNAP"))
    }
    environment.update(PYTHONPATH="", PYTHONNOUSERSITE="1")
    with TemporaryDirectory(prefix="pyao-wheel-validation-") as temporary:
        work = Path(temporary)
        environment["PYAO_STATE_DIR"] = str(work / "operator-state")
        venv = work / "environment"
        _run([uv, "venv", "--python", sys.executable, str(venv)], cwd=work, environment=environment)
        scripts = venv / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        _run(
            [uv, "pip", "install", "--python", str(python), "--require-hashes", "-r", "-"],
            cwd=work,
            environment=environment,
            input_text=runtime_lock,
        )
        _run(
            [uv, "pip", "install", "--python", str(python), "--no-deps", str(wheel)],
            cwd=work,
            environment=environment,
        )
        proof = json.loads(
            _run(
                [str(python), "-c", PROBE, identity[1]], cwd=work, environment=environment
            ).stdout.splitlines()[-1]
        )
        entry = scripts / ("pyao-server.exe" if os.name == "nt" else "pyao-server")
        _run([str(entry), "--help"], cwd=work, environment=environment)
        _run([str(entry), "--check-resources"], cwd=work, environment=environment)
    result = {
        "project": PROJECT,
        "version": identity[1],
        "platform": platform,
        "verified_install": True,
        "probe": proof,
        "files": [{"name": path.name, "sha256": _sha(path)} for path in (wheel, source)],
    }
    (directory / "manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def assemble(directory: Path, output: Path, canonical: str) -> None:
    """Preserva nombres dentro de contenedores por OS y publica un conjunto canónico.

    Raises:
        ValueError: Ante archivos sin validar, hash cambiado, plataforma repetida o salida ocupada.
    """
    records: dict[str, tuple[dict[str, Any], list[Path], Path]] = {}
    for manifest in sorted(directory.glob("*/manifest.json")):
        record = json.loads(manifest.read_text())
        platform = record["platform"]
        if (
            not record.get("verified_install")
            or not PLATFORM_PATTERN.fullmatch(platform)
            or platform in records
        ):
            message = "Artefacto sin validación o plataforma repetida/inválida"
            raise ValueError(message)
        paths = []
        for entry in record["files"]:
            filename = entry["name"]
            if Path(filename).name != filename:
                message = "Nombre de artefacto inválido"
                raise ValueError(message)
            path = manifest.parent / filename
            if _sha(path) != entry["sha256"] or distribution_identity(path) != (
                PROJECT,
                record["version"],
            ):
                message = "Artefacto modificado después de validar"
                raise ValueError(message)
            paths.append(path)
        if (
            len(paths) != len({path.name for path in paths})
            or sum(path.name.endswith(".whl") for path in paths) != 1
            or sum(path.name.endswith(".tar.gz") for path in paths) != 1
        ):
            message = "Manifiesto de distribución incompleto"
            raise ValueError(message)
        records[platform] = record, paths, manifest
    if canonical not in records or len({record[0]["version"] for record in records.values()}) != 1:
        message = "Falta plataforma canónica o hay versiones distintas"
        raise ValueError(message)
    if output.exists() and any(output.iterdir()):
        message = "No se sobreescriben assets de una release existente"
        raise ValueError(message)
    output.mkdir(parents=True, exist_ok=True)
    for path in records[canonical][1]:
        shutil.copyfile(path, output / path.name)
    for platform, (record, paths, manifest) in records.items():
        bundle = output / f"{PROJECT}-{record['version']}-{platform}.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in [*paths, manifest]:
                archive.write(path, path.name)
    sums = "".join(f"{_sha(path)}  {path.name}\n" for path in sorted(output.iterdir()))
    (output / "SHA256SUMS").write_text(sums)


def main() -> None:
    """Expone validación y ensamblado sin modificar los nombres del backend."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    check = commands.add_parser("validate")
    check.add_argument("--directory", type=Path, default=Path("dist"))
    check.add_argument("--platform", required=True)
    merge = commands.add_parser("assemble")
    merge.add_argument("--directory", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--canonical", default="ubuntu-24.04")
    args = parser.parse_args()
    if args.command == "validate":
        print(json.dumps(validate(args.directory.resolve(), args.platform), indent=2))
    else:
        assemble(args.directory.resolve(), args.output.resolve(), args.canonical)


if __name__ == "__main__":
    main()
