"""Paquetes de canales derivados de candidatos nativos, sin publicarlos.

El servidor incorpora Python privado y dependencias del lock. Ninguna receta
descarga paquetes al arrancar ni instala/inicia Redis. La promoción requiere
pruebas del par; construir estos candidatos nunca cambia un canal público.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import stat
import subprocess
import sys
from tempfile import TemporaryDirectory
import tomllib
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = re.compile(r"^(\d+\.\d+\.\d+)(?:rc(\d+))?$")
PLATFORMS = {"Linux": "linux", "Darwin": "macos", "Windows": "windows"}
# Deflating tiny INSTALLER/zip-safe metadata can increase its size by 2x/3x;
# WinGet's ZIP validator rejects that negative compression ratio (#396).
ZIP_MIN_DEFLATE_BYTES = 64


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(arguments: list[str], **kwargs: Any) -> str:
    output: str = subprocess.check_output(arguments, text=True, **kwargs)
    return output.strip()


def product_version(value: str) -> str:
    if VERSION.fullmatch(value) is None:
        raise ValueError("Versión de producto inválida")
    return value


def deb_version(value: str) -> str:
    return product_version(value).replace("rc", "~rc")


def deb_asset_name(archive: str) -> str:
    """Nombre externo estable en GitHub; la versión interna conserva el tilde."""
    public_name = archive.replace("~", ".")
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*\.deb", public_name) is None:
        raise ValueError("Nombre de paquete Debian no seguro")
    return public_name


def native_target() -> str:
    architecture = {"x86_64": "amd64", "AMD64": "amd64", "aarch64": "arm64", "arm64": "arm64"}.get(
        platform.machine()
    )
    if architecture is None or platform.system() not in PLATFORMS:
        raise ValueError("Plataforma nativa no soportada")
    return PLATFORMS[platform.system()] + "-" + architecture


def file_inventory(root: Path) -> dict[str, str]:
    files = {}
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Enlace fuera del paquete: " + name)
            files[name] = "symlink:" + os.readlink(path)
        elif path.is_file() and name not in {
            "server-candidate.json",
            "server-proof.json",
            "candidate-manifest.json",
        }:
            files[name] = sha(path)
    return files


def verify_inventory(root: Path, expected: dict[str, str]) -> None:
    if file_inventory(root) != expected:
        raise ValueError("El candidato cambió después de construirse")


def compiler_environment() -> dict[str, str]:
    environment = dict(os.environ)
    if shutil.which("cl"):
        return environment
    finder = (
        Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
        / "Microsoft Visual Studio/Installer/vswhere.exe"
    )
    installation = run(
        [
            str(finder),
            "-latest",
            "-products",
            "*",
            "-requires",
            "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
            "-property",
            "installationPath",
        ]
    )
    setup = Path(installation) / "VC/Auxiliary/Build/vcvars64.bat"
    if not setup.is_file():
        raise RuntimeError("Falta el compilador C de Visual Studio")
    # A fixed batch filename avoids list2cmdline escaping quotes as \\" inside
    # cmd.exe's command language. The working directory can still contain spaces.
    with TemporaryDirectory(prefix="pyao-msvc-") as temporary:
        bootstrap = Path(temporary) / "pyao-env.cmd"
        bootstrap.write_text(
            f'@echo off\ncall "{setup}" >nul\nif errorlevel 1 exit /b %errorlevel%\nset\n',
            encoding="utf-8",
        )
        output = run(
            [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/u", "/c", bootstrap.name],
            cwd=temporary,
            encoding="utf-16-le",
        )
    for line in output.splitlines():
        key, separator, value = line.partition("=")
        if separator and key:
            environment[key.upper()] = value
    return environment


def build_server(wheel: Path, output: Path, tray: Path | None = None) -> dict[str, Any]:
    if output.exists():
        raise ValueError("El directorio del candidato debe ser nuevo")
    version = product_version(
        tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]["version"]
    )
    with zipfile.ZipFile(wheel) as archive:
        metadata = [n for n in archive.namelist() if n.endswith(".dist-info/METADATA")]
        if len(metadata) != 1 or f"Version: {version}\n" not in archive.read(metadata[0]).decode():
            raise ValueError("El wheel no corresponde a la versión del servidor")
        if "Name: pyao-server\n" not in archive.read(metadata[0]).decode():
            raise ValueError("El wheel no es del servidor")
    prefix = Path(sys.base_prefix).resolve()
    if not prefix.name.startswith("cpython-") or not prefix.is_dir():
        raise ValueError(
            "Construir con el Python administrado por uv, no copiar Python del sistema"
        )
    output.mkdir(parents=True)
    runtime = output / "python"
    shutil.copytree(prefix, runtime, symlinks=True)
    executable = runtime / ("python.exe" if os.name == "nt" else "bin/python3")
    environment = dict(os.environ, PYTHONPATH="", PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1")
    site = Path(
        run(
            [
                str(executable),
                "-I",
                "-B",
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ],
            env=environment,
        )
    ).resolve()
    if not site.is_relative_to(runtime.resolve()):
        raise ValueError("El intérprete no es reubicable")
    if site.exists():
        shutil.rmtree(site)
    site.mkdir(parents=True)
    requirements = output / "runtime-requirements.txt"
    requirements.write_text(
        run(
            ["uv", "export", "--locked", "--no-dev", "--no-emit-project", "--extra", "desktop"],
            cwd=ROOT,
        )
        + "\n"
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(executable),
            "--target",
            str(site),
            "--require-hashes",
            "--only-binary",
            ":all:",
            "-r",
            str(requirements),
        ],
        check=True,
        env=environment,
    )
    subprocess.run(
        [
            "uv",
            "pip",
            "install",
            "--python",
            str(executable),
            "--target",
            str(site),
            "--no-deps",
            str(wheel),
        ],
        check=True,
        env=environment,
    )
    if os.name == "nt":
        compiler = compiler_environment()
        executable_compiler = shutil.which("cl.exe", path=compiler.get("PATH"))
        if executable_compiler is None:
            raise RuntimeError("El entorno de Visual Studio no contiene cl.exe")
        with TemporaryDirectory(prefix="pyao-launcher-") as temporary:
            subprocess.run(
                [
                    executable_compiler,
                    "/nologo",
                    "/O2",
                    "/MT",
                    "/W4",
                    "/WX",
                    str(ROOT / "desktop/server_launcher_windows.c"),
                    "/Fepyao-server.exe",
                    "/link",
                    "/SUBSYSTEM:CONSOLE",
                ],
                cwd=temporary,
                env=compiler,
                check=True,
            )
            shutil.copy2(Path(temporary) / "pyao-server.exe", output / "pyao-server.exe")
        shutil.copy2(output / "pyao-server.exe", output / "pyao-server-indicator.exe")
    else:
        for name, module in {
            "pyao-server": "src.run_server",
            "pyao-server-indicator": "src.desktop.indicator",
        }.items():
            launcher = output / name
            launcher.write_text(
                '#!/bin/sh\nset -eu\nroot=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nunset PYTHONPATH PYTHONHOME\nexport PYTHONNOUSERSITE=1 PYTHONDONTWRITEBYTECODE=1\nexport PATH="$root:$PATH"\nexec "$root/python/bin/python3" -I -B -X utf8 -m '
                + module
                + ' "$@"\n'
            )
            launcher.chmod(0o755)
    if platform.system() == "Linux":
        if tray is None or not tray.is_file():
            raise ValueError("El candidato Linux requiere su puente de bandeja nativo")
        shutil.copy2(tray, output / "pyao-tray")
        (output / "pyao-tray").chmod(0o755)
    shutil.copy2(ROOT / "LICENSE", output / "LICENSE")
    (output / "README.txt").write_text(
        f"PyAO Server {version}\nRedis es externo. Este paquete no lo instala ni lo inicia.\nLa configuración y partida se conservan en las rutas del usuario y en Redis.\nUsar el cliente de la misma versión.\n"
    )
    record = {
        "version": version,
        "commit": run(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "dirty": bool(run(["git", "status", "--porcelain"], cwd=ROOT)),
        "platform": native_target(),
        "wheel_sha256": sha(wheel),
        "python": sys.version,
        "python_path": executable.relative_to(output).as_posix(),
        "files": file_inventory(output),
        "verified": False,
    }
    (output / "server-candidate.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def validate_server(candidate: Path, output: Path) -> dict[str, Any]:
    record = json.loads((candidate / "server-candidate.json").read_text())
    verify_inventory(candidate, record["files"])
    if record["platform"] != native_target():
        raise ValueError("El servidor requiere validación en su plataforma nativa")
    with TemporaryDirectory(prefix="PyAO servidor con espacios ") as temporary:
        work = Path(temporary)
        runtime = work / "Servidor listo"
        shutil.copytree(candidate, runtime, symlinks=True)
        executable = runtime / ("pyao-server.exe" if os.name == "nt" else "pyao-server")
        environment = {
            k: v for k, v in os.environ.items() if not k.startswith(("PYAO_", "PYTHON", "SNAP"))
        }
        environment["PYAO_STATE_DIR"] = str(work / "state")
        version = run([str(executable), "--version"], cwd=work, env=environment)
        if not version.endswith(record["version"]):
            raise ValueError("La versión ejecutada difiere del candidato")
        run([str(executable), "--help"], cwd=work, env=environment)
        run([str(executable), "--check-resources"], cwd=work, env=environment)
        probe = run(
            [
                str(runtime / record["python_path"]),
                "-I",
                "-B",
                "-c",
                "import src,sys; from pathlib import Path; assert Path(src.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()); print(src.__version__)",
            ],
            cwd=work,
            env=environment,
        )
        if probe != record["version"]:
            raise ValueError("El paquete importó fuentes externas")
    proof = {
        "passed": True,
        "version": record["version"],
        "server_commit": record["commit"],
        "platform": record["platform"],
        "candidate_manifest_sha256": sha(candidate / "server-candidate.json"),
        "outside_checkout": True,
        "redis_installed_or_started": False,
    }
    output.write_text(json.dumps(proof, indent=2) + "\n")
    verify_inventory(candidate, record["files"])
    return proof


def archive_tree(source: Path, output: Path) -> None:
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(source.rglob("*")):
            if path.is_symlink():
                info = zipfile.ZipInfo(path.relative_to(source).as_posix())
                info.create_system = 3
                info.external_attr = (stat.S_IFLNK | 0o777) << 16
                archive.writestr(info, os.readlink(path))
            elif path.is_file():
                method = (
                    zipfile.ZIP_STORED
                    if path.stat().st_size < ZIP_MIN_DEFLATE_BYTES
                    else zipfile.ZIP_DEFLATED
                )
                archive.write(path, path.relative_to(source).as_posix(), compress_type=method)


def seal_server(candidate: Path, cli_proof: Path, pair_proof: Path, output: Path) -> dict[str, Any]:
    record = json.loads((candidate / "server-candidate.json").read_text())
    cli, pair = (json.loads(p.read_text()) for p in (cli_proof, pair_proof))
    if (
        record["dirty"]
        or cli.get("passed") is not True
        or cli.get("candidate_manifest_sha256") != sha(candidate / "server-candidate.json")
    ):
        raise ValueError("Falta una prueba CLI del candidato limpio")
    if not (
        pair.get("regression_passed") is True
        and pair.get("tls") is True
        and pair.get("installed_wheel") is True
        and pair.get("server_commit") == record["commit"]
        and pair.get("release_version") == record["version"]
        and pair.get("server_candidate_sha256") == sha(candidate / "server-candidate.json")
    ):
        raise ValueError("Falta la prueba del mismo servidor privado con los dos clientes")
    verify_inventory(candidate, record["files"])
    output.mkdir(parents=True, exist_ok=True)
    path = output / f"pyao-server-{record['version']}-{record['platform']}.zip"
    if path.exists():
        raise ValueError("No se sobrescribe un artefacto sellado")
    archive_tree(candidate, path)
    result = {
        **record,
        "verified": True,
        "archive": path.name,
        "sha256": sha(path),
        "cli_proof_sha256": sha(cli_proof),
        "pair_proof_sha256": sha(pair_proof),
        "paired_client_commit": pair["client_commit"],
    }
    path.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def build_deb(candidate: Path, role: str, proof_path: Path, output: Path) -> dict[str, Any]:
    server = role == "server"
    record = json.loads(
        (candidate / ("server-candidate.json" if server else "candidate-manifest.json")).read_text()
    )
    proof = json.loads(proof_path.read_text())
    platform_name = record["platform"]
    if platform_name not in {"linux", "linux-arm64", "linux-amd64"} or record["dirty"]:
        raise ValueError("Se requiere un candidato Linux limpio")
    if proof.get("passed") is not True or proof.get("candidate_manifest_sha256") != sha(
        candidate / ("server-candidate.json" if server else "candidate-manifest.json")
    ):
        raise ValueError("Falta una prueba de este candidato")
    verify_inventory(candidate, record["files"])
    architecture = "arm64" if platform_name.endswith("arm64") else "amd64"
    name = "pyao-server" if server else "pyao-client"
    version = product_version(record["version"])
    output.mkdir(parents=True, exist_ok=True)
    destination = output / deb_asset_name(f"{name}_{deb_version(version)}_{architecture}.deb")
    if destination.exists():
        raise ValueError("No se sobrescribe un paquete Debian")
    with TemporaryDirectory(prefix="pyao-deb-") as temporary:
        root = Path(temporary)
        payload = root / "opt" / name
        payload.parent.mkdir(parents=True)
        shutil.copytree(candidate, payload, symlinks=True)
        copyright_path = root / f"usr/share/doc/{name}/copyright"
        copyright_path.parent.mkdir(parents=True)
        shutil.copy2(payload / "LICENSE", copyright_path)
        executable = (
            "pyao-server"
            if server
            else "pyao-client.arm64"
            if architecture == "arm64"
            else "pyao-client.x86_64"
        )
        binary = root / "usr/bin" / name
        binary.parent.mkdir(parents=True)
        binary.write_text(f'#!/bin/sh\nexec /opt/{name}/{executable} "$@"\n')
        binary.chmod(0o755)
        if server:
            icon = next(
                payload.glob(
                    "python/lib/python*/site-packages/src/runtime_data/data/desktop/icons/pyao-server-128.png"
                )
            )
            desktop_command = "/opt/pyao-server/pyao-server-indicator"
            unit = root / "usr/lib/systemd/user/pyao-server.service"
            unit.parent.mkdir(parents=True)
            unit.write_text(
                "[Unit]\nDescription=PyAO Server\nAfter=network-online.target\n\n"
                "[Service]\nType=simple\n"
                'Environment="PYAO_SERVER_ARGS=--host 127.0.0.1"\n'
                "EnvironmentFile=-%h/.config/pyao-server/service.env\n"
                "ExecStart=/usr/bin/pyao-server $PYAO_SERVER_ARGS\n"
                "Restart=on-failure\nRestartSec=5\nNoNewPrivileges=true\n\n"
                "[Install]\nWantedBy=default.target\n"
            )
        else:
            icon = payload / "pyao-client.png"
            desktop_command = "/usr/bin/pyao-client"
        icon_target = root / f"usr/share/icons/hicolor/128x128/apps/{name}.png"
        icon_target.parent.mkdir(parents=True)
        shutil.copy2(icon, icon_target)
        desktop = root / f"usr/share/applications/{name}.desktop"
        desktop.parent.mkdir(parents=True)
        desktop.write_text(
            f"[Desktop Entry]\nType=Application\nName={'PyAO Server' if server else 'PyAO Client'}\nExec={desktop_command}\nIcon={name}\nTerminal=false\nCategories={'Network;' if server else 'Game;RolePlaying;'}\n"
        )
        control = root / "DEBIAN/control"
        control.parent.mkdir()
        dependencies = "libc6 (>= 2.39), libstdc++6, libgcc-s1"
        recommendations = "Recommends: libayatana-appindicator3-1\n" if server else ""
        if not server:
            dependencies += ", libayatana-appindicator3-1, libgl1, libvulkan1, libx11-6, libxcursor1, libxi6, libxinerama1, libxrandr2, libxkbcommon0, libwayland-client0, libpulse0, libasound2t64 | libasound2"
        control.write_text(
            f"Package: {name}\nVersion: {deb_version(version)}\nArchitecture: {architecture}\nMaintainer: PyAO Project <cavazquez@users.noreply.github.com>\nSection: {'net' if server else 'games'}\nPriority: optional\nDepends: {dependencies}\n{recommendations}Homepage: https://github.com/cavazquez/{'pyao-server' if server else 'ArgentumOnlineGodot'}\nDescription: {'Argentum Online server with a private Python runtime; Redis is external' if server else 'Argentum Online Godot client with embedded game resources'}\n"
        )
        subprocess.run(
            ["dpkg-deb", "--root-owner-group", "--build", str(root), str(destination)], check=True
        )
    result = {
        "project": name,
        "version": version,
        "debian_version": deb_version(version),
        "architecture": architecture,
        "commit": record["commit"],
        "candidate_manifest_sha256": sha(
            candidate / ("server-candidate.json" if server else "candidate-manifest.json")
        ),
        "native_proof_sha256": sha(proof_path),
        "archive": destination.name,
        "sha256": sha(destination),
        "verified_install": False,
        "user_data_name": record.get("user_data_name") if not server else None,
    }
    destination.with_suffix(".json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    build = commands.add_parser("server")
    build.add_argument("--wheel", type=Path, required=True)
    build.add_argument("--tray", type=Path)
    for name in ("server", "validate-server", "seal-server", "deb"):
        command = build if name == "server" else commands.add_parser(name)
        command.add_argument("--output", type=Path, required=True)
        if name != "server":
            command.add_argument("--candidate", type=Path, required=True)
        if name in {"seal-server", "deb"}:
            command.add_argument("--proof", type=Path, required=True)
        if name == "seal-server":
            command.add_argument("--pair-proof", type=Path, required=True)
        if name == "deb":
            command.add_argument("--role", choices=("server", "client"), required=True)
    args = parser.parse_args()
    if args.action == "server":
        result = build_server(args.wheel.resolve(), args.output.resolve(), args.tray)
    elif args.action == "validate-server":
        result = validate_server(args.candidate.resolve(), args.output.resolve())
    elif args.action == "seal-server":
        result = seal_server(
            args.candidate.resolve(),
            args.proof.resolve(),
            args.pair_proof.resolve(),
            args.output.resolve(),
        )
    else:
        result = build_deb(
            args.candidate.resolve(), args.role, args.proof.resolve(), args.output.resolve()
        )
    summary = {**result}
    if "files" in summary:
        summary["files"] = len(summary["files"])
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
