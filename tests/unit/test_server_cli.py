"""Tests para ServerCLI."""

import logging
from unittest.mock import patch

import pytest

from src.server_cli import ServerCLI


class TestServerCLI:
    """Tests para ServerCLI."""

    def test_init(self) -> None:
        """Test de inicialización."""
        cli = ServerCLI()

        assert cli.logger is not None
        assert cli.parser is not None
        assert cli.VERSION is not None

    def test_create_parser(self) -> None:
        """Test de creación del parser."""
        cli = ServerCLI()
        parser = cli.parser

        assert parser is not None
        assert parser.description is not None

    def test_parse_args_defaults(self) -> None:
        """Test de parsing con valores por defecto."""
        cli = ServerCLI()

        with patch("sys.argv", ["pyao-server"]):
            args = cli.parse_args()

            assert args.debug is False
            assert args.host == "0.0.0.0"
            assert args.port == 7666
            assert args.ssl is False
            assert args.ssl_cert is None
            assert args.ssl_key is None

    def test_parse_args_debug(self) -> None:
        """Test de parsing con flag debug."""
        cli = ServerCLI()

        with patch("sys.argv", ["pyao-server", "--debug"]):
            args = cli.parse_args()

            assert args.debug is True

    def test_parse_args_custom_host(self) -> None:
        """Test de parsing con host personalizado."""
        cli = ServerCLI()

        with patch("sys.argv", ["pyao-server", "--host", "127.0.0.1"]):
            args = cli.parse_args()

            assert args.host == "127.0.0.1"

    def test_parse_args_custom_port(self) -> None:
        """Test de parsing con puerto personalizado."""
        cli = ServerCLI()

        with patch("sys.argv", ["pyao-server", "--port", "8000"]):
            args = cli.parse_args()

            assert args.port == 8000

    def test_parse_args_all_options(self) -> None:
        """Test de parsing con todas las opciones."""
        cli = ServerCLI()

        with patch(
            "sys.argv",
            [
                "pyao-server",
                "--debug",
                "--host",
                "localhost",
                "--port",
                "9000",
                "--ssl",
                "--ssl-cert",
                "custom.crt",
                "--ssl-key",
                "custom.key",
            ],
        ):
            args = cli.parse_args()

            assert args.debug is True
            assert args.host == "localhost"
            assert args.port == 9000
            assert args.ssl is True
            assert args.ssl_cert == "custom.crt"
            assert args.ssl_key == "custom.key"

    def test_configure_logging_info(self) -> None:
        """Test de configuración de logging en modo INFO."""
        cli = ServerCLI()

        with patch("src.logging_config.configure_logging") as mock_configure:
            cli.configure_logging(debug=False)

            # Verifica que configure_logging() fue llamado
            mock_configure.assert_called_once()

    def test_configure_logging_debug(self) -> None:
        """Test de configuración de logging en modo DEBUG."""
        cli = ServerCLI()

        with patch("src.logging_config.configure_logging") as mock_configure, \
             patch("src.logging_config.verbose_mode") as mock_verbose:
            cli.configure_logging(debug=True)

            # Verifica que configure_logging() y verbose_mode() fueron llamados
            mock_configure.assert_called_once()
            mock_verbose.assert_called_once()

    def test_version_attribute(self) -> None:
        """Test que VERSION está definida."""
        cli = ServerCLI()

        assert isinstance(cli.VERSION, str)
        assert len(cli.VERSION) > 0

    def test_parser_help_text(self) -> None:
        """Test que el parser tiene texto de ayuda."""
        cli = ServerCLI()

        # Verificar que tiene descripción
        assert "PyAO Server" in cli.parser.description

        # Verificar que tiene epilog con ejemplos
        assert cli.parser.epilog is not None
        assert "Ejemplos:" in cli.parser.epilog

    def test_parse_args_version(self) -> None:
        """Test del flag --version."""
        cli = ServerCLI()

        with patch("sys.argv", ["pyao-server", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                cli.parse_args()

            # --version causa SystemExit con código 0
            assert exc_info.value.code == 0
