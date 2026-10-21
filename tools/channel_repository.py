"""Prepara el tap, manifiestos WinGet y repositorio APT de un par aprobado.

Sólo consume archivos sellados; no construye ejecutables ni realiza publicación.
APT se sirve como repositorio plano desde assets de la release apt-edge del tap.
Cada paquete conserva además su URL inmutable en la release de producto.
"""

import argparse
from datetime import UTC, datetime
from email.utils import format_datetime
import gzip
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from tools.package_channels import product_version, sha

CHANNEL_REPOSITORY = "cavazquez/homebrew-pyao"
REPOSITORIES = {"server": "cavazquez/pyao-server", "client": "cavazquez/ArgentumOnlineGodot"}
SCHEMA_VERSION = "1.10.0"


def read_artifact(path: Path, version: str, commit: str, *, deb: bool = False) -> dict[str, Any]:
    record: dict[str, Any] = json.loads(path.read_text())
    if (
        record.get("version") != version
        or record.get("commit") != commit
        or record.get("dirty", False)
    ):
        raise ValueError("Artefacto de otra versión, commit o fuentes sucias")
    if record.get("verified_install" if deb else "verified") is not True:
        raise ValueError("Artefacto sin validación de instalación")
    name = record.get("archive", "")
    if not name or Path(name).name != name:
        raise ValueError("Nombre de artefacto inválido")
    archive = path.parent / name
    if not archive.is_file() or sha(archive) != record.get("sha256"):
        raise ValueError("Artefacto cambiado después de probarse")
    return {**record, "path": archive, "manifest_sha256": sha(path)}


def package_key(record: dict[str, Any], role: str) -> str:
    target = str(record["platform"])
    if role == "server":
        return target
    if target == "macos":
        for suffix, architecture in (("-arm64.zip", "arm64"), ("-x86_64.zip", "amd64")):
            if record["archive"].endswith(suffix):
                return "macos-" + architecture
        raise ValueError("Falta arquitectura del bundle macOS")
    return {"linux": "linux-amd64", "linux-arm64": "linux-arm64", "windows": "windows-amd64"}[
        target
    ]


def url(record: dict[str, Any], role: str, version: str) -> str:
    repository = CHANNEL_REPOSITORY if role == "server" else REPOSITORIES["client"]
    return f"https://github.com/{repository}/releases/download/v{version}/{record['archive']}"


def app_name(record: dict[str, Any]) -> str:
    names: set[str] = {
        name.split("/")[0] for name in record["files"] if name.split("/")[0].endswith(".app")
    }
    if len(names) != 1:
        raise ValueError("Bundle macOS ambiguo")
    name = names.pop()
    if re.fullmatch(r"[A-Za-z0-9 ._-]+\.app", name) is None:
        raise ValueError("Nombre de bundle no permitido")
    return name


def write_homebrew(
    output: Path,
    records: dict[str, dict[str, dict[str, Any]]],
    version: str,
    architectures: tuple[str, ...] = ("arm64", "amd64"),
) -> None:
    client = records["client"]
    for folder in ("Formula", "Casks"):
        (output / folder).mkdir(parents=True)
    formula = [
        "class PyaoServer < Formula",
        '  desc "Servidor de Argentum Online con Python privado; Redis es externo"',
        '  homepage "https://github.com/cavazquez/pyao-server"',
        f'  version "{version}"',
        '  license "Apache-2.0"',
        "  depends_on :macos",
    ]
    cask = [
        'cask "pyao-client" do',
        f'  version "{version}"',
        '  name "PyAO Client"',
        '  desc "Cliente de Argentum Online"',
        '  homepage "https://github.com/cavazquez/ArgentumOnlineGodot"',
    ]
    bundles = []
    for architecture in architectures:
        condition = "on_arm" if architecture == "arm64" else "on_intel"
        for lines, role in ((formula, "server"), (cask, "client")):
            record = records[role]["macos-" + architecture]
            lines.extend(
                [
                    f"  {condition} do",
                    f'    url "{url(record, role, version)}"',
                    f'    sha256 "{record["sha256"]}"',
                    "  end",
                ]
            )
        bundles.append(app_name(client["macos-" + architecture]))
    if len(set(bundles)) != 1:
        raise ValueError("Los bundles macOS difieren entre arquitecturas")
    formula.extend(
        [
            "  def install",
            '    libexec.install Dir["*"]',
            '    bin.write_exec_script libexec/"pyao-server"',
            '    bin.write_exec_script libexec/"pyao-server-indicator"',
            "  end",
            "  def caveats",
            '    "Redis es externo; instalarlo y configurarlo por separado. El paquete no inicia Redis."',
            "  end",
            "  test do",
            '    ENV["PYAO_STATE_DIR"] = testpath/"state"',
            '    assert_match version.to_s, shell_output("#{bin}/pyao-server --version")',
            '    system bin/"pyao-server", "--check-resources"',
            "  end",
            "end",
            "",
        ]
    )
    cask.extend([f'  app "{bundles[0]}"', "end", ""])
    (output / "Formula/pyao-server.rb").write_text("\n".join(formula))
    (output / "Casks/pyao-client.rb").write_text("\n".join(cask))


def write_winget(output: Path, records: dict[str, dict[str, dict[str, Any]]], version: str) -> None:
    for role, identifier, title in (
        ("server", "Cavazquez.PyAOServer", "PyAO Server"),
        ("client", "Cavazquez.PyAOClient", "PyAO Client"),
    ):
        windows = records[role]["windows-amd64"]
        directory = output / "winget" / identifier / version
        directory.mkdir(parents=True)
        shared = {"PackageIdentifier": identifier, "PackageVersion": version}
        manifests = {
            identifier + ".yaml": {
                **shared,
                "DefaultLocale": "es-AR",
                "ManifestType": "version",
                "ManifestVersion": SCHEMA_VERSION,
            },
            identifier + ".installer.yaml": {
                **shared,
                "InstallerType": "zip",
                "NestedInstallerType": "portable",
                "Installers": [
                    {
                        "Architecture": "x64",
                        "InstallerUrl": url(windows, role, version),
                        "InstallerSha256": windows["sha256"].upper(),
                        "NestedInstallerFiles": [
                            {
                                "RelativeFilePath": "pyao-server.exe"
                                if role == "server"
                                else "pyao-client.exe",
                                "PortableCommandAlias": "pyao-server"
                                if role == "server"
                                else "pyao-client",
                            }
                        ],
                    }
                ],
                "ManifestType": "installer",
                "ManifestVersion": SCHEMA_VERSION,
            },
            identifier + ".locale.es-AR.yaml": {
                **shared,
                "PackageLocale": "es-AR",
                "Publisher": "PyAO Project",
                "PackageName": title,
                "License": "Apache-2.0" if role == "server" else "MIT",
                "LicenseUrl": f"https://github.com/{REPOSITORIES[role]}/blob/v{version}/LICENSE",
                "ShortDescription": "Servidor de Argentum Online; Redis es externo."
                if role == "server"
                else "Cliente de Argentum Online con gráficos y recursos incluidos.",
                "PackageUrl": f"https://github.com/{REPOSITORIES[role]}",
                "ManifestType": "defaultLocale",
                "ManifestVersion": SCHEMA_VERSION,
            },
        }
        # JSON is a YAML subset. This avoids dependencies and quotes every scalar.
        for name, manifest in manifests.items():
            (directory / name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")


def write_recipes(
    output: Path, records: dict[str, dict[str, dict[str, Any]]], version: str
) -> None:
    write_homebrew(output, records, version)
    write_winget(output, records, version)


def verify_installation_checks(
    plan: dict[str, Any],
    base: Path,
    records: dict[str, dict[str, dict[str, Any]]],
    debs: list[dict[str, Any]],
) -> None:
    expected = {
        ("apt", "linux-amd64"),
        ("apt", "linux-arm64"),
        ("homebrew", "macos-amd64"),
        ("homebrew", "macos-arm64"),
        ("winget", "windows-amd64"),
    }
    checked: set[tuple[str, str]] = set()
    for relative in plan["checks"]:
        proof = json.loads((base / relative).resolve().read_text())
        key = (proof.get("channel"), proof.get("platform"))
        if (
            key not in expected
            or key in checked
            or proof.get("sources") != plan["sources"]
            or proof.get("version") != plan["version"]
        ):
            raise ValueError("Prueba de instalación duplicada o de otro par")
        if not all(
            proof.get(flag) is True
            for flag in (
                "passed",
                "installed",
                "upgraded",
                "removed",
                "configuration_preserved",
                "preferences_preserved",
            )
        ):
            raise ValueError("Prueba de instalación incompleta")
        if key[0] == "apt":
            packages = {
                r["archive"]: r["sha256"] for r in debs if "linux-" + r["architecture"] == key[1]
            }
            if not packages or proof.get("packages") != packages:
                raise ValueError("APT probó otros paquetes")
        else:
            for role in ("server", "client"):
                artifact = records[role][key[1]]
                if (
                    proof.get(role + "_sha256") != artifact["sha256"]
                    or proof.get(role + "_manifest_sha256") != artifact["manifest_sha256"]
                ):
                    raise ValueError("Homebrew/WinGet probó otros archivos")
        checked.add(key)
    if checked != expected:
        raise ValueError("Faltan plataformas de instalación")


def prepare(plan_path: Path, output: Path) -> dict[str, Any]:
    if output.exists():
        raise ValueError("La salida debe ser nueva")
    plan = json.loads(plan_path.read_text())
    version = product_version(plan["version"])
    commits = plan["sources"]
    if set(commits) != {"server", "client"} or any(
        re.fullmatch(r"[0-9a-f]{40}", value) is None for value in commits.values()
    ):
        raise ValueError("Se requieren los commits completos del par")
    if len(plan.get("checks", [])) != 5:
        raise ValueError(
            "Se requieren cinco pruebas de instalación: dos APT, dos Homebrew y WinGet"
        )
    records: dict[str, dict[str, dict[str, Any]]] = {"server": {}, "client": {}}
    for role in records:
        for relative in plan[role]:
            record = read_artifact((plan_path.parent / relative).resolve(), version, commits[role])
            paired = record.get("paired_client_commit" if role == "server" else "server_commit")
            if paired != commits["client" if role == "server" else "server"]:
                raise ValueError("El candidato se probó con otro par")
            key = package_key(record, role)
            if key in records[role]:
                raise ValueError("Plataforma duplicada")
            records[role][key] = record
        if set(records[role]) != {
            "linux-amd64",
            "linux-arm64",
            "macos-amd64",
            "macos-arm64",
            "windows-amd64",
        }:
            raise ValueError("Faltan plataformas nativas del par")
    debs = []
    for relative in plan["debs"]:
        path = (plan_path.parent / relative).resolve()
        initial = json.loads(path.read_text())
        role = {"pyao-server": "server", "pyao-client": "client"}[initial["project"]]
        debs.append(read_artifact(path, version, commits[role], deb=True))
    if {(r["project"], r["architecture"]) for r in debs} != {
        (p, a) for p in ("pyao-server", "pyao-client") for a in ("amd64", "arm64")
    } or len(debs) != 4:
        raise ValueError("El repositorio APT requiere ambos paquetes y arquitecturas")
    verify_installation_checks(plan, plan_path.parent, records, debs)
    output.mkdir(parents=True)
    write_recipes(output, records, version)
    apt = output / "apt"
    apt.mkdir()
    packages = []
    for record in sorted(debs, key=lambda r: r["archive"]):
        path = record["path"]
        shutil.copy2(path, apt / path.name)
        control: str = subprocess.check_output(["dpkg-deb", "--field", str(path)], text=True)
        packages.append(
            control.rstrip()
            + f"\nFilename: {path.name}\nSize: {path.stat().st_size}\nSHA256: {sha(path)}\n"
        )
    (apt / "Packages").write_text("\n".join(packages) + "\n")
    (apt / "Packages.gz").write_bytes(gzip.compress((apt / "Packages").read_bytes(), mtime=0))
    hashes = "".join(
        f" {sha(apt / name)} {int((apt / name).stat().st_size)} {name}\n"
        for name in ("Packages", "Packages.gz")
    )
    (apt / "Release").write_text(
        f"Origin: PyAO\nLabel: PyAO edge\nSuite: edge\nCodename: edge\nDate: {format_datetime(datetime.now(UTC))}\nArchitectures: amd64 arm64\nDescription: PyAO coordinated prereleases\nSHA256:\n{hashes}"
    )
    assets = output / "release-assets"
    assets.mkdir()
    for record in records["server"].values():
        shutil.copy2(record["path"], assets / record["archive"])
    for record in debs:
        shutil.copy2(record["path"], assets / record["archive"])
    result = {
        "version": version,
        "sources": commits,
        "repository": CHANNEL_REPOSITORY,
        "promoted": False,
        "artifacts": {p.name: sha(p) for p in sorted(assets.iterdir())},
        "apt_packages": {r["archive"]: r["sha256"] for r in debs},
        "client_release_urls": {
            key: url(record, "client", version) for key, record in records["client"].items()
        },
    }
    (output / "channel-manifest.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def native_recipes(server_path: Path, client_path: Path, output: Path) -> dict[str, Any]:
    initial = json.loads(server_path.read_text())
    version = product_version(initial["version"])
    server = read_artifact(server_path, version, initial["commit"])
    client = read_artifact(client_path, version, server["paired_client_commit"])
    if client["server_commit"] != server["commit"]:
        raise ValueError("Los instaladores se probaron con pares distintos")
    target = package_key(server, "server")
    if target != package_key(client, "client"):
        raise ValueError("Las arquitecturas nativas de los instaladores difieren")
    records = {"server": {target: server}, "client": {target: client}}
    output.mkdir(parents=True, exist_ok=False)
    if target.startswith("macos-"):
        write_homebrew(output, records, version, (target.removeprefix("macos-"),))
    elif target == "windows-amd64":
        write_winget(output, records, version)
    else:
        raise ValueError("APT tiene una prueba de instalación separada")
    user_name = client.get("user_data_name", "")
    if (
        not user_name
        or user_name in {".", ".."}
        or re.fullmatch(r"[A-Za-z0-9 ._-]+", user_name) is None
    ):
        raise ValueError("Falta el directorio de preferencias de producción del cliente")
    return {
        "version": version,
        "platform": target,
        "server_commit": server["commit"],
        "client_commit": client["commit"],
        "client_user_data_name": user_name,
        "server_manifest_sha256": sha(server_path),
        "client_manifest_sha256": sha(client_path),
        "server_archive": str(server["path"].resolve()),
        "client_archive": str(client["path"].resolve()),
        "server_sha256": server["sha256"],
        "client_sha256": client["sha256"],
    }


def sign_apt(directory: Path, key: str, gpg_home: Path) -> None:
    if re.fullmatch(r"[A-Fa-f0-9]{40}|[A-Fa-f0-9]{64}", key) is None:
        raise ValueError("Usar la huella completa de la clave APT")
    arguments = ["gpg", "--homedir", str(gpg_home), "--batch", "--local-user", key]
    subprocess.run(
        [
            *arguments,
            "--armor",
            "--export",
            "--output",
            str(directory / "pyao-archive-key.asc"),
            key,
        ],
        check=True,
    )
    subprocess.run(
        [
            *arguments,
            "--armor",
            "--detach-sign",
            "--output",
            str(directory / "Release.gpg"),
            str(directory / "Release"),
        ],
        check=True,
    )
    subprocess.run(
        [
            *arguments,
            "--clearsign",
            "--output",
            str(directory / "InRelease"),
            str(directory / "Release"),
        ],
        check=True,
    )
    subprocess.run(
        ["gpg", "--homedir", str(gpg_home), "--batch", "--verify", str(directory / "InRelease")],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    build = commands.add_parser("prepare")
    build.add_argument("--plan", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    sign = commands.add_parser("sign-apt")
    sign.add_argument("--directory", type=Path, required=True)
    sign.add_argument("--key", required=True)
    sign.add_argument("--gpg-home", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        print(json.dumps(prepare(args.plan.resolve(), args.output.resolve()), indent=2))
    else:
        sign_apt(args.directory.resolve(), args.key, args.gpg_home.resolve())


if __name__ == "__main__":
    main()
