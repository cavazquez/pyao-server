"""Prueba Homebrew/WinGet sólo en runners descartables, con los archivos sellados."""

import argparse
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
from collections.abc import Iterator
from typing import Any

from tools.channel_repository import native_recipes, read_winget_manifest, write_winget_manifest
from tools.package_channels import sha


def call(arguments: list[str], **kwargs: Any) -> str:
    try:
        result: str = subprocess.check_output(
            arguments, text=True, stderr=subprocess.STDOUT, **kwargs
        )
    except subprocess.CalledProcessError as error:
        print(error.output, file=sys.stderr)
        raise
    return result


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format: str, *args: Any) -> None:
        pass


@contextmanager
def archive_server(directory: Path) -> Iterator[str]:
    with ThreadingHTTPServer(
        ("127.0.0.1", 0), partial(QuietHandler, directory=str(directory))
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=10)


def verify(server_manifest: Path, client_manifest: Path, output: Path) -> dict[str, Any]:
    if os.environ.get("GITHUB_ACTIONS") != "true":
        raise RuntimeError("Esta prueba de instaladores modifica sólo runners descartables de CI")
    original = output / "production-recipes"
    record = native_recipes(server_manifest, client_manifest, original)
    server = Path(record["server_archive"])
    client = Path(record["client_archive"])
    logs = []
    if platform.system() == "Darwin":
        preferences = (
            Path.home()
            / "Library/Application Support/Godot/app_userdata"
            / record["client_user_data_name"]
            / "options.cfg"
        )
        preferences.parent.mkdir(parents=True, exist_ok=True)
        preferences.write_text('[channel_validation]\nkeep="PYAO_CHANNEL_UPGRADE_SENTINEL"\n')
        tap_name = "cavazquez/pyao-validation"
        logs.append(call(["brew", "tap-new", "--no-git", tap_name]))
        tap = Path(call(["brew", "--repository", tap_name]).strip())
        environment = dict(
            os.environ, HOMEBREW_NO_AUTO_UPDATE="1", PYAO_STATE_DIR=str(output / "state")
        )
        for directory in ("Formula", "Casks"):
            (tap / directory).mkdir(parents=True, exist_ok=True)
            for source in (original / directory).glob("*.rb"):
                text = source.read_text()
                text = text.replace(
                    f"https://github.com/cavazquez/homebrew-pyao/releases/download/v{record['version']}/{server.name}",
                    server.as_uri(),
                )
                text = text.replace(
                    f"https://github.com/cavazquez/ArgentumOnlineGodot/releases/download/v{record['version']}/{client.name}",
                    client.as_uri(),
                )
                (tap / directory / source.name).write_text(text)
        formula = tap / "Formula/pyao-server.rb"
        current_formula = formula.read_text().replace(
            f'  version "{record["version"]}"', f'  version "{record["version"]}"\n  revision 1'
        )
        cask = tap / "Casks/pyao-client.rb"
        current_cask = cask.read_text()
        cask.write_text(
            current_cask.replace(f'  version "{record["version"]}"', '  version "0.0.0"')
        )
        try:
            logs.append(
                call(["brew", "install", "--formula", f"{tap_name}/pyao-server"], env=environment)
            )
            logs.append(
                call(["brew", "install", "--cask", f"{tap_name}/pyao-client"], env=environment)
            )
            entry = (
                Path(call(["brew", "--prefix", "pyao-server"], env=environment).strip())
                / "bin/pyao-server"
            )
            logs.append(call([str(entry), "--check-resources"], env=environment))
            config = output / "state/config/server.toml"
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text('[server]\nhost = "127.0.0.1"\n\n# preserve channel upgrade\n')
            before = sha(config)
            formula.write_text(current_formula)
            cask.write_text(current_cask)
            logs.append(
                call(["brew", "upgrade", "--formula", f"{tap_name}/pyao-server"], env=environment)
            )
            logs.append(
                call(["brew", "upgrade", "--cask", f"{tap_name}/pyao-client"], env=environment)
            )
            logs.append(call(["brew", "test", f"{tap_name}/pyao-server"], env=environment))
            if sha(config) != before:
                raise ValueError("La actualización Homebrew cambió la configuración")
            client_record = json.loads(client_manifest.read_text())
            app_names = {
                name.split("/")[0]
                for name in client_record["files"]
                if name.split("/")[0].endswith(".app")
            }
            app = Path("/Applications") / next(iter(app_names))
            executables = [p for p in (app / "Contents/MacOS").iterdir() if p.is_file()]
            if len(executables) != 1:
                raise ValueError("Ejecutable del cask ambiguo")
            logs.append(
                call(
                    [
                        str(executables[0]),
                        "--audio-driver",
                        "Dummy",
                        "--rendering-method",
                        "gl_compatibility",
                        "--quit-after",
                        "45",
                    ],
                    timeout=90,
                    env=environment,
                )
            )
            if sha(config) != before:
                raise ValueError("La apertura del cliente cambió la configuración del servidor")
        finally:
            logs.append(
                call(["brew", "uninstall", "--cask", f"{tap_name}/pyao-client"], env=environment)
            )
            logs.append(
                call(["brew", "uninstall", "--formula", f"{tap_name}/pyao-server"], env=environment)
            )
        if sha(config) != before:
            raise ValueError("Desinstalar Homebrew borró la configuración")
        if "PYAO_CHANNEL_UPGRADE_SENTINEL" not in preferences.read_text():
            raise ValueError("Homebrew no conservó las preferencias del cliente")
        record.update(
            installed=True,
            upgraded=True,
            removed=True,
            configuration_preserved=True,
            preferences_preserved=True,
            channel="homebrew",
            notarized=False,
            download_fixture="file URLs to the same sealed archives; no Internet quarantine claim",
        )
    elif platform.system() == "Windows":
        downloads = output / "downloads"
        downloads.mkdir()
        for archive in (server, client):
            shutil.copy2(archive, downloads / archive.name)
        with archive_server(downloads) as address:
            for fixture, version in (("baseline", "0.0.0"), ("current", record["version"])):
                for source in (original / "winget").rglob("*.yaml"):
                    value = read_winget_manifest(source)
                    value["PackageVersion"] = version
                    for installer in value.get("Installers", []):
                        installer["InstallerUrl"] = (
                            address + "/" + installer["InstallerUrl"].rsplit("/", 1)[1]
                        )
                    path = output / fixture / value["PackageIdentifier"] / source.name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    write_winget_manifest(path, value)
            logs.append(
                call(
                    [
                        "pwsh",
                        "-NoProfile",
                        "-File",
                        str(Path(__file__).with_name("check_winget.ps1")),
                        "-Directory",
                        str(output),
                        "-Version",
                        record["version"],
                        "-UserDataName",
                        record["client_user_data_name"],
                    ],
                    timeout=900,
                )
            )
        details = json.loads((output / "winget-proof.json").read_text())
        if details.get("passed") is not True:
            raise ValueError("WinGet no terminó la prueba de ambos paquetes")
        record.update(details, channel="winget")
    else:
        raise ValueError("APT usa la prueba de contenedores específica")
    log = output / "installer.log"
    log.write_text("\n".join(logs))
    if any(
        error in log.read_text()
        for error in (
            "SCRIPT ERROR:",
            "ERROR:",
            "ObjectDB instances leaked",
            "Resources still in use",
        )
    ):
        raise ValueError("Un instalador o aplicación registró un error")
    record.update(
        passed=True,
        sources={"server": record["server_commit"], "client": record["client_commit"]},
        log_sha256=sha(log),
        upgrade_fixture="previous packaging revision of the same approved bytes; not a previous game release",
        artifact_rebuilt=False,
    )
    (output / "native-channel-proof.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", type=Path, required=True)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(
        json.dumps(
            verify(args.server.resolve(), args.client.resolve(), args.output.resolve()), indent=2
        )
    )
