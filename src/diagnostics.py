"""Diagnóstico de sólo lectura: no usa inicializador, seeds, migraciones ni listener."""

import argparse
import asyncio
import inspect
import ssl
from pathlib import Path

from redis.asyncio import Redis
from redis.exceptions import RedisError

from src import __version__
from src.runtime_paths import data_dir, maps_dir, state_dir


async def diagnose(args: argparse.Namespace) -> dict[str, object]:
    """Comprueba dependencias con timeout y devuelve únicamente datos autorizados.

    Returns:
        Informe público con estado y diagnóstico de cada dependencia.
    """
    checks: list[dict[str, object]] = []
    try:
        from src.config.game_config import (  # ruff: ignore[import-outside-top-level] - frontera de diagnóstico
            get_game_config,
        )

        config = get_game_config()
        checks.append({"name": "configuration", "ok": True})
    except (OSError, ValueError, RuntimeError, ImportError) as error:
        checks.append(
            {
                "name": "configuration",
                "ok": False,
                "message": f"Revisar TOML y entorno ({type(error).__name__})",
            }
        )
        config = None
    try:
        from src.validation.dataset import (  # ruff: ignore[import-outside-top-level] - frontera de diagnóstico
            DatasetValidator,
        )

        report = DatasetValidator(data_dir(), maps_dir()).validate()
        checks.append(
            {
                "name": "dataset",
                "ok": not report.errors,
                "message": "Ejecutar --check-resources para el detalle"
                if report.errors
                else "Datos válidos",
            }
        )
    except (OSError, ValueError, RuntimeError, KeyError) as error:
        checks.append(
            {
                "name": "dataset",
                "ok": False,
                "message": f"Revisar --data-dir/--maps-dir ({type(error).__name__})",
            }
        )
    if config is not None:
        client = None
        try:
            r = config.redis
            client = Redis(
                host=r.host,
                port=r.port,
                db=r.db,
                password=r.read_password(),
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            async with asyncio.timeout(4):
                pending = client.ping()
                result = await pending if inspect.isawaitable(pending) else pending
            checks.append({"name": "redis", "ok": bool(result)})
        except (RedisError, TimeoutError, OSError, ValueError) as error:
            checks.append(
                {
                    "name": "redis",
                    "ok": False,
                    "message": "Revisar servicio, endpoint y secreto Redis "
                    f"({type(error).__name__})",
                }
            )
        finally:
            if client:
                await client.aclose()
    if args.ssl:
        try:
            cert = Path(args.ssl_cert) if args.ssl_cert else state_dir() / "certs/server.crt"
            key = Path(args.ssl_key) if args.ssl_key else state_dir() / "certs/server.key"
            ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(cert, key)
            checks.append({"name": "tls", "ok": True})
        except (OSError, ValueError) as error:
            checks.append(
                {
                    "name": "tls",
                    "ok": False,
                    "message": "Revisar certificado y clave TLS; no se generan automáticamente "
                    f"({type(error).__name__})",
                }
            )
    return {"version": __version__, "ok": all(row["ok"] for row in checks), "checks": checks}
