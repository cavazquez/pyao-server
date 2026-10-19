#!/usr/bin/env python3
"""Prueba el Snap instalado contra Redis descartable, con TLS y reinicio real."""

import argparse
import hashlib
import json
import os
import shutil
import signal
import socket
import ssl
import subprocess
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from src.operations.redis_sandbox import RedisSandbox


def run_snap(app: str, arguments: list[str], env: dict[str, str], cwd: Path) -> str:
    """Ejecuta una operación del paquete instalado fuera del checkout."""
    return subprocess.check_output(
        ["snap", "run", app, *arguments], env=env, cwd=cwd, text=True, timeout=90
    )


def wait_for_tls(process: subprocess.Popen, port: int, cert: Path) -> None:
    """Espera un PONG del servidor instalado mediante una conexión TLS verificada."""
    context = ssl.create_default_context(cafile=cert)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"El Snap terminó antes de abrir TLS: {process.returncode}")
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as connection:
                with context.wrap_socket(connection, server_hostname="localhost") as peer:
                    peer.sendall(bytes([119]))
                    if peer.recv(1) != bytes([88]):
                        raise RuntimeError("El Snap no respondió PONG al PING")
                    return
        except ConnectionError, TimeoutError:
            time.sleep(0.2)
    raise TimeoutError("El Snap no abrió TLS en 90 segundos")


def main() -> None:
    """Verifica recursos, TLS, estado Redis y configuración conservados al reiniciar."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    common = Path.home() / "snap/pyao/common"
    common.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith(("PYAO_", "SNAP"))}
    with TemporaryDirectory(prefix="package-smoke-", dir=common) as directory:
        work = Path(directory)
        env["PYAO_STATE_DIR"] = str(work)
        interpreter_probe = """set -eu
for name in python python3 python3.14; do
    executable="$SNAP/bin/$name"
    resolved=$(readlink -f "$executable")
    case "$resolved" in "$SNAP"/*) ;; *) exit 1 ;; esac
    "$executable" -c 'import sys; assert sys.version_info[:2] == (3, 14)'
done
"""
        subprocess.run(
            ["snap", "run", "--shell", "pyao.pyao-server", "-c", interpreter_probe],
            env=env,
            cwd=work,
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        assert run_snap("pyao.pyao-server", ["--version"], env, work).strip().endswith("1.0.0rc1")
        invalid = work / "invalid-server.toml"
        invalid.write_text("[game.character]\nmana_per_int = 50000\n")
        informational_env = dict(env, PYAO_CONFIG_FILE=str(invalid))
        assert (
            run_snap("pyao.pyao-server", ["--version"], informational_env, work)
            .strip()
            .endswith("1.0.0rc1")
        )
        assert "--config-file" in run_snap("pyao.pyao-server", ["--help"], informational_env, work)
        run_snap("pyao.pyao-server", ["--check-resources"], env, work)
        config = work / "config/server.toml"
        config.write_text(config.read_text() + "\n# Configuración conservada por smoke Snap\n")
        config_hash = hashlib.sha256(config.read_bytes()).hexdigest()
        cert, key = work / "certs/test.crt", work / "certs/test.key"
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-days",
                "1",
                "-subj",
                "/CN=localhost",
                "-addext",
                "subjectAltName=DNS:localhost",
                "-keyout",
                str(key),
                "-out",
                str(cert),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        with RedisSandbox() as sandbox:
            secret = work / "redis-password"
            shutil.copyfile(sandbox.password_file, secret)
            secret.chmod(0o600)
            env.update(
                PYAO_REDIS__HOST="127.0.0.1",
                PYAO_REDIS__PORT=str(sandbox.port),
                PYAO_REDIS__PASSWORD_FILE=str(secret),
            )
            for attempt in (1, 2):
                with (output / f"server-{attempt}.log").open("w") as log:
                    process = subprocess.Popen(
                        [
                            "snap",
                            "run",
                            "pyao.pyao-server",
                            "--host",
                            "127.0.0.1",
                            "--port",
                            str(port),
                            "--ssl",
                            "--ssl-cert",
                            str(cert),
                            "--ssl-key",
                            str(key),
                        ],
                        env=env,
                        cwd=work,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                    try:
                        wait_for_tls(process, port, cert)
                        with sandbox.client() as client:
                            assert client.hget("schema:state", "version") == "4"
                            assert client.exists("config:skills:rules")
                            assert client.exists("config:crafting:recipes")
                            if attempt == 1:
                                client.set("validation:snap-marker", "preserved")
                            else:
                                assert client.get("validation:snap-marker") == "preserved"
                    finally:
                        if process.poll() is None:
                            process.send_signal(signal.SIGTERM)
                        try:
                            process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            process.wait(timeout=5)
                            raise
                    assert process.returncode == 0, f"Salida de Snap: {process.returncode}"
                assert hashlib.sha256(config.read_bytes()).hexdigest() == config_hash
        result = {
            "version": "1.0.0rc1",
            "installed_snap": True,
            "resources_valid": True,
            "python_aliases_inside_snap": True,
            "informational_cli_ignores_invalid_config": True,
            "tls_ping": True,
            "restarted": True,
            "redis_state_preserved": True,
            "configuration_preserved": True,
            "schema": 4,
            "graceful_sigterm": True,
            "production_data_used": False,
        }
        (output / "snap-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
