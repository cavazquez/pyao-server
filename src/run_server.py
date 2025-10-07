"""Script para ejecutar el servidor de Argentum Online."""

import asyncio
import logging

from src.server import ArgentumServer

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Punto de entrada principal del servidor."""
    logger.info("Iniciando PyAO Server...")

    server = ArgentumServer(host="0.0.0.0", port=7666)

    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception:
        logger.exception("Error fatal")
        raise


if __name__ == "__main__":
    main()
