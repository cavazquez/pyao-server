"""Script para ejecutar el servidor de Argentum Online."""

import asyncio
import logging

from src.server import ArgentumServer
from src.server_cli import ServerCLI

logger = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada principal del servidor."""
    cli = ServerCLI()
    args = cli.parse_args()

    # Configurar logging
    cli.configure_logging(args.debug)

    # Mostrar información de inicio
    logger.info("Iniciando PyAO Server v%s...", cli.VERSION)
    logger.info("Host: %s | Puerto: %d", args.host, args.port)

    # Crear y ejecutar servidor
    server = ArgentumServer(host=args.host, port=args.port)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception:
        logger.exception("Error fatal")
        raise


if __name__ == "__main__":
    main()
