"""Script para ejecutar el servidor de Argentum Online."""

import asyncio
import logging
import sys
from pathlib import Path

from src.security.ssl_manager import SSLConfigurationError, SSLManager
from src.server import ArgentumServer
from src.server_cli import ServerCLI

logger = logging.getLogger(__name__)

DEFAULT_CERT_PATH = Path("certs/server.crt")
DEFAULT_KEY_PATH = Path("certs/server.key")


def main() -> None:
    """Punto de entrada principal del servidor."""
    cli = ServerCLI()
    args = cli.parse_args()

    # Configurar logging
    cli.configure_logging(args.debug)

    ssl_manager = SSLManager(
        enabled=args.ssl,
        cert_path=Path(args.ssl_cert).expanduser() if args.ssl_cert else None,
        key_path=Path(args.ssl_key).expanduser() if args.ssl_key else None,
        default_cert_path=DEFAULT_CERT_PATH,
        default_key_path=DEFAULT_KEY_PATH,
        auto_generate=True,
    )

    try:
        ssl_manager.prepare()
    except SSLConfigurationError:
        logger.exception("Error preparando la configuración SSL")
        sys.exit(1)

    ssl_cert_path = ssl_manager.cert_path
    ssl_key_path = ssl_manager.key_path

    # Mostrar información de inicio
    logger.info("Iniciando PyAO Server v%s...", cli.VERSION)
    logger.info("Host: %s | Puerto: %d", args.host, args.port)
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

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception:
        logger.exception("Error fatal")
        raise


if __name__ == "__main__":
    main()
