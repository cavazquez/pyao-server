"""Interfaz de línea de comandos para el servidor."""

import argparse
import logging

from src import __version__
from src.logging_config import configure_logging, verbose_mode


class ServerCLI:
    """Interfaz de línea de comandos para el servidor."""

    VERSION = __version__

    def __init__(self) -> None:
        """Inicializa la CLI del servidor."""
        self.logger = logging.getLogger(__name__)
        self.parser = self._create_parser()

    def _create_parser(self) -> argparse.ArgumentParser:
        """Crea el parser de argumentos de línea de comandos.

        Returns:
            Parser configurado con todos los argumentos.
        """
        parser = argparse.ArgumentParser(
            description="PyAO Server - Servidor de Argentum Online en Python",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Ejemplos:
  pyao-server                    # Iniciar servidor en modo normal
  pyao-server --debug            # Iniciar con logs de debug
  pyao-server --host 127.0.0.1   # Iniciar en localhost
  pyao-server --port 8000        # Usar puerto personalizado
            """,
        )
        parser.add_argument(
            "--debug",
            action="store_true",
            help="Habilitar logs de debug (muestra información detallada)",
        )
        parser.add_argument(
            "--host",
            type=str,
            default="0.0.0.0",
            help="Host donde escuchar (default: 0.0.0.0)",
        )
        parser.add_argument(
            "--port",
            type=int,
            default=7666,
            help="Puerto donde escuchar (default: 7666)",
        )
        parser.add_argument(
            "--ssl",
            action="store_true",
            help="Habilitar TLS/SSL para el socket del servidor",
        )
        parser.add_argument(
            "--ssl-cert",
            type=str,
            default=None,
            help="Ruta al certificado PEM del servidor (default: certs/server.crt)",
        )
        parser.add_argument(
            "--ssl-key",
            type=str,
            default=None,
            help="Ruta a la clave privada PEM del servidor (default: certs/server.key)",
        )
        parser.add_argument(
            "--version",
            action="version",
            version=f"PyAO Server {self.VERSION}",
        )
        return parser

    def _configure_logging(self, debug: bool) -> None:
        """Configura el sistema de logging.

        Args:
            debug: Si True, habilita logs de nivel DEBUG para todo.
        """
        # Configurar logging por features
        configure_logging()

        # Si debug está activado, poner todo en modo verbose
        if debug:
            verbose_mode()

        if debug:
            self.logger.info("🐛 Modo DEBUG habilitado - Mostrando logs detallados")

    def parse_args(self) -> argparse.Namespace:
        """Parsea los argumentos de línea de comandos.

        Returns:
            Namespace con los argumentos parseados.
        """
        return self.parser.parse_args()

    def configure_logging(self, debug: bool) -> None:
        """Configura el sistema de logging (método público).

        Args:
            debug: Si True, habilita logs de nivel DEBUG.
        """
        self._configure_logging(debug)
