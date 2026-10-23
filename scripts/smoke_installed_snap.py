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

from src import __version__
from src.core.schema_manager import CURRENT_SCHEMA_VERSION, SCHEMA_KEY
from src.economy.taxes import DEFAULT_RATE_BPS, TAX_POLICY_KEY
from src.operations.redis_sandbox import RedisSandbox


def run_snap(app: str, arguments: list[str], env: dict[str, str], cwd: Path) -> str:
    """Ejecuta una operación del paquete instalado fuera del checkout."""
    return subprocess.check_output(
        ["snap", "run", app, *arguments], env=env, cwd=cwd, text=True, timeout=90
    )


def wait_for_tls(process: subprocess.Popen[bytes], port: int, cert: Path) -> None:
    """Espera un PONG del servidor instalado mediante una conexión TLS verificada."""
    context = ssl.create_default_context(cafile=cert)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    # El primer arranque migra el stock completo antes de admitir conexiones.
    deadline = time.monotonic() + 240
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
    raise TimeoutError("El Snap no abrió TLS en 240 segundos")


def signal_snap(process: subprocess.Popen[bytes], value: signal.Signals) -> None:
    """Señaliza sólo el proceso propio, también desde un perfil AppArmor diferente."""
    try:
        process.send_signal(value)
    except PermissionError:
        # Snap admite señales del mismo perfil. Una sesión con un perfil propio
        # puede lanzar la app pero no señalizarla directamente desde fuera.
        subprocess.run(
            [
                "snap",
                "run",
                "--shell",
                "pyao.pyao-server",
                "-c",
                'kill -s "$1" "$2"',
                "pyao-smoke-stop",
                value.name.removeprefix("SIG"),
                str(process.pid),
            ],
            check=True,
            timeout=15,
        )


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
        assert run_snap("pyao.pyao-server", ["--version"], env, work).strip().endswith(__version__)
        invalid = work / "invalid-server.toml"
        invalid.write_text("[game.character]\nmana_per_int = 50000\n")
        informational_env = dict(env, PYAO_CONFIG_FILE=str(invalid))
        assert (
            run_snap("pyao.pyao-server", ["--version"], informational_env, work)
            .strip()
            .endswith(__version__)
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
            preserved = {}
            preserved_strings = {
                "config:crafting:recipes": "[]",
                "server:motd": "Bienvenido a Argentum Online!\nServidor en desarrollo.",
                "server:dice:min_value": "0",
                "config:effects:hunger_thirst:enabled": "0",
            }
            preserved_hashes = {
                "world:home:1": {"map": "34", "x": "0"},
                "player:812:user_stats": {"gold": "0", "level": "35", "experience": "1234"},
                "player:812:inventory": {"slot_30": "15:2"},
                "player:812:equipment": {"weapon": "30"},
                "player:812:bank_inventory": {"slot_1": "38:3"},
                "merchant:7:inventory": {"slot_1": "", "slot_20": "139:3"},
            }
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
                            assert client.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION)
                            assert client.exists("config:skills:rules")
                            assert client.exists("config:crafting:recipes")
                            assert client.hget(TAX_POLICY_KEY, "enabled") == "1"
                            assert client.hget(TAX_POLICY_KEY, "rate_bps") == str(DEFAULT_RATE_BPS)
                            assert client.hget(TAX_POLICY_KEY, "ground_activation_day")
                            if attempt == 1:
                                client.set("validation:snap-marker", "preserved")
                                for name, value in preserved_strings.items():
                                    client.set(name, value)
                                for name, fields in preserved_hashes.items():
                                    client.hset(name, mapping=fields)
                                client.expire("server:motd", 3600)
                                preserved = {
                                    name: client.hgetall(name)
                                    for name in (*preserved_hashes, "merchant:7:catalog")
                                }
                                client.delete("world:home:6", "server:dice:max_value")
                            else:
                                assert client.get("validation:snap-marker") == "preserved"
                                for name, value in preserved_strings.items():
                                    assert client.get(name) == value, name
                                for name, fields in preserved.items():
                                    assert client.hgetall(name) == fields, name
                                assert 3500 <= client.ttl("server:motd") <= 3600
                                assert client.hget("world:home:6", "map") == "151"
                                assert client.get("server:dice:max_value") == "18"
                    finally:
                        if process.poll() is None:
                            signal_snap(process, signal.SIGTERM)
                        try:
                            process.wait(timeout=30)
                        except subprocess.TimeoutExpired:
                            signal_snap(process, signal.SIGKILL)
                            process.wait(timeout=5)
                            raise
                    assert process.returncode == 0, f"Salida de Snap: {process.returncode}"
                assert hashlib.sha256(config.read_bytes()).hexdigest() == config_hash
        result = {
            "version": __version__,
            "installed_snap": True,
            "resources_valid": True,
            "python_aliases_inside_snap": True,
            "informational_cli_ignores_invalid_config": True,
            "tls_ping": True,
            "restarted": True,
            "redis_state_preserved": True,
            "bootstrap_preserves_custom_values_and_ttl": True,
            "bootstrap_completes_missing_defaults": True,
            "bootstrap_preserves_depleted_merchant_stock": True,
            "daily_devaluation_policy": True,
            "configuration_preserved": True,
            "schema": CURRENT_SCHEMA_VERSION,
            "graceful_sigterm": True,
            "production_data_used": False,
        }
        (output / "snap-smoke.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps(result))


if __name__ == "__main__":
    main()
