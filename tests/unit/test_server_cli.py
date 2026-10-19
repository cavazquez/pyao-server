"""Tests para ServerCLI."""

import os
import subprocess  # noqa: S404 - procesos nuevos del propio intérprete, sin shell.
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from src.server_cli import ServerCLI


@pytest.mark.parametrize("flag", ["--version", "--help"])
@pytest.mark.parametrize("configuration", ["[game.character]\nmana_per_int = 50000\n", "[invalid"])
def test_informational_cli_does_not_initialize_game(
    tmp_path: Path, flag: str, configuration: str
) -> None:
    """Un proceso nuevo consulta ayuda/versión con TOML roto, sin cargar Redis."""
    invalid = tmp_path / "server.toml"
    invalid.write_text(configuration)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYAO_")}
    environment.update(
        PYTHONPATH=str(Path(__file__).resolve().parents[2]),
        PYAO_CONFIG_FILE=str(invalid),
        PYAO_REDIS__HOST="unreachable.invalid",
        PYAO_REDIS__PASSWORD_FILE=str(tmp_path / "missing-redis-secret"),
    )
    code = """import sys
from src.run_server import main
try:
    main()
finally:
    assert 'src.config.game_config' not in sys.modules
    assert 'src.utils.redis_client' not in sys.modules
"""
    result = subprocess.run(  # noqa: S603 - intérprete actual y argumentos propios.
        [sys.executable, "-c", code, flag],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert ("PyAO Server" if flag == "--version" else "--config-file") in result.stdout
    assert invalid.read_text() == configuration


def test_config_file_override_precedes_singleton_initialization(tmp_path: Path) -> None:
    """La ruta CLI reemplaza un TOML inválido heredado antes de inicializarlo."""
    invalid, selected = tmp_path / "invalid.toml", tmp_path / "selected.toml"
    invalid.write_text("[game.character]\nmana_per_int = 50000\n")
    selected.write_text("[game.character]\nmana_per_int = 11\n")
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYAO_")}
    environment.update(
        PYTHONPATH=str(Path(__file__).resolve().parents[2]), PYAO_CONFIG_FILE=str(invalid)
    )
    code = """from src.run_server import main
try:
    main()
except SystemExit as result:
    if result.code:
        raise
from src.config.game_config import game_config
assert game_config.game.character.mana_per_int == 11
"""
    result = subprocess.run(  # noqa: S603 - intérprete actual y rutas temporales propias.
        [sys.executable, "-c", code, "--config-file", str(selected), "--check-resources"],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr


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
            assert args.host is None
            assert args.port is None
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

        with patch("src.server_cli.configure_logging") as mock_configure:
            cli.configure_logging(debug=False)

            # Verifica que configure_logging() fue llamado
            mock_configure.assert_called_once()

    def test_configure_logging_debug(self) -> None:
        """Test de configuración de logging en modo DEBUG."""
        cli = ServerCLI()

        with (
            patch("src.server_cli.configure_logging") as mock_configure,
            patch("src.server_cli.verbose_mode") as mock_verbose,
        ):
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
