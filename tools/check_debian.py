"""Instalación/actualización/desinstalación del par Debian en contenedores propios."""

import argparse
import json
from pathlib import Path
import re
import subprocess
from typing import Any
from uuid import uuid4

from tools.package_channels import sha

IMAGES = ("ubuntu:24.04", "debian:trixie-slim")
SCRIPT = r"""
set -eu
export DEBIAN_FRONTEND=noninteractive
export PYAO_STATE_DIR=/tmp/pyao-state
export XDG_CONFIG_HOME=/tmp/pyao-preferences
export XDG_DATA_HOME=/tmp/pyao-user-data
apt-get update -qq
apt-get install -y --no-install-recommends xvfb xauth libgl1-mesa-dri mesa-vulkan-drivers
mkdir -p /tmp/baseline /tmp/fixture-packages /tmp/pyao-state /tmp/pyao-preferences
mkdir -p "$XDG_DATA_HOME/godot/app_userdata/$2"
preferences="$XDG_DATA_HOME/godot/app_userdata/$2/options.cfg"
printf '[channel_validation]\nkeep="PYAO_CHANNEL_UPGRADE_SENTINEL"\n' > "$preferences"
for package in /packages/*.deb; do
    name=$(dpkg-deb -f "$package" Package)
    package_version=$(dpkg-deb -f "$package" Version)
    dpkg-deb -R "$package" "/tmp/baseline/$name"
    sed -i "s/^Version: .*/Version: ${package_version}~fixture0/" "/tmp/baseline/$name/DEBIAN/control"
    dpkg-deb --root-owner-group --build "/tmp/baseline/$name" "/tmp/fixture-packages/$name.deb"
done
# A packaging-only previous revision exercises upgrade without pretending that
# an earlier release of this brand-new distribution channel already existed.
apt-get install -y --no-install-recommends /tmp/fixture-packages/*.deb
pyao-server --version
pyao-server --check-resources
mkdir -p /tmp/pyao-state/config
printf '# User configuration\n[server]\nhost = "127.0.0.1"\n\n# Preserve packaging upgrade\n' > /tmp/pyao-state/config/server.toml
printf 'keep\n' > /tmp/pyao-preferences/pyao-upgrade-marker
configuration_before=$(sha256sum /tmp/pyao-state/config/server.toml)
apt-get install -y --no-install-recommends /packages/*.deb
test "$configuration_before" = "$(sha256sum /tmp/pyao-state/config/server.toml)"
pyao-server --version | grep -F "$1"
pyao-server --check-resources
test "$configuration_before" = "$(sha256sum /tmp/pyao-state/config/server.toml)"
client=$(command -v pyao-client)
xvfb-run -a -s '-screen 0 1024x768x24' "$client" --audio-driver Dummy --rendering-method gl_compatibility --quit-after 45 >/tmp/pyao-client.log 2>&1
cat /tmp/pyao-client.log
if grep -E '(^|[[:space:]])(ERROR:|SCRIPT ERROR:)' /tmp/pyao-client.log; then exit 1; fi
test "$(cat /tmp/pyao-preferences/pyao-upgrade-marker)" = keep
grep -F PYAO_CHANNEL_UPGRADE_SENTINEL "$preferences"
apt-get remove -y pyao-server pyao-client
test ! -e /opt/pyao-server
test ! -e /opt/pyao-client
test "$configuration_before" = "$(sha256sum /tmp/pyao-state/config/server.toml)"
test "$(cat /tmp/pyao-preferences/pyao-upgrade-marker)" = keep
grep -F PYAO_CHANNEL_UPGRADE_SENTINEL "$preferences"
printf 'PYAO_DEBIAN_INSTALL_UPGRADE_REMOVE: PASS\n'
"""


def verify(directory: Path, output: Path) -> dict[str, Any]:
    packages = sorted(directory.glob("*.deb"))
    if len(packages) != 2:
        raise ValueError("Se requieren exactamente servidor y cliente de la arquitectura nativa")
    records = [json.loads(p.with_suffix(".json").read_text()) for p in packages]
    versions = {r["version"] for r in records}
    architectures = {r["architecture"] for r in records}
    if (
        len(versions) != 1
        or len(architectures) != 1
        or {r["project"] for r in records} != {"pyao-server", "pyao-client"}
    ):
        raise ValueError("Los paquetes Debian no son un par de la misma versión/arquitectura")
    user_name = next(r.get("user_data_name", "") for r in records if r["project"] == "pyao-client")
    if (
        not user_name
        or user_name in {".", ".."}
        or re.fullmatch(r"[A-Za-z0-9 ._-]+", user_name) is None
    ):
        raise ValueError("Falta el directorio de preferencias del cliente")
    for package, record in zip(packages, records, strict=True):
        if sha(package) != record["sha256"]:
            raise ValueError("El paquete Debian cambió")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for image in IMAGES:
        name = "pyao-deb-validation-" + uuid4().hex
        log = output / (image.replace(":", "-") + ".log")
        try:
            with log.open("w") as stream:
                subprocess.run(
                    [
                        "docker",
                        "run",
                        "--rm",
                        "--name",
                        name,
                        "--mount",
                        f"type=bind,src={directory.resolve()},dst=/packages,readonly",
                        image,
                        "sh",
                        "-c",
                        SCRIPT,
                        "pyao-deb-check",
                        next(iter(versions)),
                        user_name,
                    ],
                    check=True,
                    text=True,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=900,
                )
            if "PYAO_DEBIAN_INSTALL_UPGRADE_REMOVE: PASS" not in log.read_text():
                raise ValueError("La imagen no completó la prueba del par")
            image_digest = subprocess.check_output(
                ["docker", "image", "inspect", image, "--format", "{{json .RepoDigests}}"],
                text=True,
            ).strip()
            results.append(
                {
                    "image": image,
                    "digests": json.loads(image_digest),
                    "passed": True,
                    "log_sha256": sha(log),
                }
            )
        finally:
            # Only the random identity created in this iteration is addressed.
            subprocess.run(
                ["docker", "rm", "-f", name],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=30,
            )
    result = {
        "channel": "apt",
        "platform": "linux-" + next(iter(architectures)),
        "sources": {
            "server" if r["project"] == "pyao-server" else "client": r["commit"] for r in records
        },
        "passed": True,
        "version": next(iter(versions)),
        "architecture": next(iter(architectures)),
        "installed": True,
        "upgraded": True,
        "upgrade_fixture": "previous packaging revision of the same approved game bytes; not a previous game release",
        "removed": True,
        "preferences_preserved": True,
        "configuration_preserved": True,
        "redis_installed_or_started": False,
        "images": results,
        "packages": {p.name: sha(p) for p in packages},
    }
    proof = output / "install-proof.json"
    proof.write_text(json.dumps(result, indent=2) + "\n")
    for package, record in zip(packages, records, strict=True):
        record.update(verified_install=True, install_proof_sha256=sha(proof))
        package.with_suffix(".json").write_text(json.dumps(record, indent=2) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.directory.resolve(), arguments.output.resolve()), indent=2))
