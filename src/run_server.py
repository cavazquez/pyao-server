"""Script para ejecutar el servidor de Argentum Online."""

# Silenciar warning de GIL en Python 3.13+ (msgpack no declara compatibilidad)
import warnings

warnings.filterwarnings("ignore", message=".*GIL.*", category=RuntimeWarning)

import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from src.runtime_paths import BUNDLED_ROOT, data_dir, maps_dir, resource_root, state_dir
from src.security.ssl_manager import SSLConfigurationError, SSLManager
from src.server_cli import ServerCLI

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    import argparse

    from src.server import ArgentumServer

DEFAULT_CERT_PATH = state_dir() / "certs/server.crt"
DEFAULT_KEY_PATH = state_dir() / "certs/server.key"


async def run_until_stopped(server: ArgentumServer) -> None:
    """Procesa SIGTERM/SIGINT y conserva el loop hasta terminar Server.stop."""
    requested = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = {}
    for number in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(number, requested.set)
        except NotImplementedError:
            previous[number] = signal.signal(
                number, lambda *_: loop.call_soon_threadsafe(requested.set)
            )
    serving = asyncio.create_task(server.start(), name="pyao-listener")
    stopping = asyncio.create_task(requested.wait(), name="pyao-stop-signal")
    try:
        done, _ = await asyncio.wait((serving, stopping), return_when=asyncio.FIRST_COMPLETED)
        if serving in done and not serving.cancelled():
            await serving
    finally:
        await server.stop()
        serving.cancel()
        stopping.cancel()
        await asyncio.gather(serving, stopping, return_exceptions=True)
        for number in (signal.SIGTERM, signal.SIGINT):
            if number in previous:
                signal.signal(number, previous[number])
            else:
                loop.remove_signal_handler(number)


def _run_diagnostic(args: argparse.Namespace) -> None:
    """Ejecuta el diagnóstico sin importar el servidor ni sus inicializadores."""
    from src.diagnostics import diagnose  # noqa: PLC0415 - preservar CLI sin configuración

    result = asyncio.run(diagnose(args))
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0 if result["ok"] else 1)


def main() -> None:
    """Punto de entrada principal del servidor."""
    cli = ServerCLI()
    args = cli.parse_args()

    for option, environment in (
        ("config_file", "PYAO_CONFIG_FILE"),
        ("data_dir", "PYAO_DATA_DIR"),
        ("maps_dir", "PYAO_MAPS_DIR"),
        ("state_dir", "PYAO_STATE_DIR"),
    ):
        if value := getattr(args, option):
            os.environ[environment] = str(Path(value).expanduser().resolve())
    if args.diagnose:
        _run_diagnostic(args)
    # Las dependencias y sus singletons leen las rutas después de parsear el CLI.
    from src.validation.dataset import DatasetValidator  # noqa: PLC0415

    report = DatasetValidator(data_dir(), maps_dir()).validate()
    if args.check_resources:
        print(json.dumps(report.to_dict(), ensure_ascii=False))
        sys.exit(1 if report.errors else 0)
    if report.errors:
        logger.error("Dataset inválido; ejecutar --check-resources para ver el diagnóstico")
        sys.exit(1)

    from src.server import ArgentumServer  # noqa: PLC0415
    from tools.compression.map_binary import ensure_binary_maps  # noqa: PLC0415
    from tools.compression.map_sync import check_map_sync_on_startup  # noqa: PLC0415

    # Configurar logging
    cli.configure_logging(args.debug)

    ssl_manager = SSLManager(
        enabled=args.ssl,
        cert_path=Path(args.ssl_cert).expanduser() if args.ssl_cert else None,
        key_path=Path(args.ssl_key).expanduser() if args.ssl_key else None,
        default_cert_path=state_dir() / "certs/server.crt",
        default_key_path=state_dir() / "certs/server.key",
        auto_generate=True,
    )

    try:
        ssl_manager.prepare()
    except SSLConfigurationError:
        logger.exception("Error preparando la configuración SSL")
        sys.exit(1)

    ssl_cert_path = ssl_manager.cert_path
    ssl_key_path = ssl_manager.key_path

    # Verificar sincronización de mapas
    logger.info("Verificando datos de mapas...")
    if not BUNDLED_ROOT.is_dir() and not check_map_sync_on_startup(
        resource_root() / "archives/map_data.xz", maps_dir()
    ):
        logger.error(
            "No se pudo inicializar map_data/. "
            "Ejecuta: uv run python -m tools.compression.map_sync status"
        )
        sys.exit(1)

    # Generar/actualizar mapas binarios si es necesario
    logger.info("Verificando mapas binarios...")
    if ensure_binary_maps(maps_dir(), state_dir() / "map_binary"):
        logger.info("✓ Mapas binarios listos")
    else:
        logger.warning("No se pudieron generar mapas binarios, usando JSON")

    # Mostrar información de inicio
    logger.info("Iniciando PyAO Server v%s...", cli.VERSION)
    if ssl_manager.enabled:
        logger.info(
            "SSL habilitado | Certificado: %s | Clave: %s",
            ssl_cert_path,
            ssl_key_path,
        )

    # Crear y ejecutar servidor
    server = ArgentumServer(
        host=args.host,
        port=args.port,
        ssl_manager=ssl_manager,
    )
    logger.info("Endpoint efectivo: %s:%d", server.host, server.port)

    try:
        asyncio.run(run_until_stopped(server))
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception:
        logger.exception("Error fatal")
        raise


if __name__ == "__main__":
    main()
