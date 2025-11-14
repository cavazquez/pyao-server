"""Tests para el sistema de configuración."""

import os
from pathlib import Path

from src.config import config_manager
from src.config.config_manager import ConfigManager


class TestConfigManager:
    """Tests para ConfigManager."""

    def test_get_server_config(self) -> None:
        """Verifica que se obtenga configuración del servidor."""
        host = config_manager.get("server.host", "localhost")
        port = config_manager.get("server.port", 7666)

        assert host in {"0.0.0.0", "localhost"}
        assert isinstance(port, int)
        assert 1024 <= port <= 65535

    def test_get_game_config(self) -> None:
        """Verifica que se obtenga configuración del juego."""
        max_players = config_manager.get("game.max_players_per_map", 100)
        melee_range = config_manager.get("game.combat.melee_range", 1)

        assert isinstance(max_players, int)
        assert max_players > 0
        assert isinstance(melee_range, int)
        assert melee_range > 0

    def test_environment_overrides(self) -> None:
        """Verifica que las variables de entorno sobrescriban la configuración."""
        # Guardar valores originales
        original_port = os.environ.get("PYAO_SERVER_PORT")
        original_log_level = os.environ.get("PYAO_LOG_LEVEL")

        # Guardar paths originales del ConfigManager
        original_config_dir = getattr(ConfigManager, "_config_dir", None)
        original_config_file = getattr(ConfigManager, "_config_file", None)

        try:
            # Setear variables de entorno de prueba
            os.environ["PYAO_SERVER_PORT"] = "8888"
            os.environ["PYAO_LOG_LEVEL"] = "DEBUG"

            # Resetear a paths por defecto para evitar usar archivo inválido de otro test
            ConfigManager._config_dir = Path(__file__).parent.parent.parent / "config"
            ConfigManager._config_file = ConfigManager._config_dir / "server.toml"

            # Limpiar singleton completamente antes de la prueba
            ConfigManager._instance = None
            ConfigManager._initialized = False
            ConfigManager._config = {}

            # Crear NUEVA instancia de ConfigManager dentro del test
            test_config = ConfigManager()

            port = test_config.get("server.port", 7666)
            log_level = test_config.get("logging.level", "INFO")

            assert port == 8888
            assert log_level == "DEBUG"

        finally:
            # Restaurar valores originales
            if original_port is not None:
                os.environ["PYAO_SERVER_PORT"] = original_port
            else:
                os.environ.pop("PYAO_SERVER_PORT", None)

            if original_log_level is not None:
                os.environ["PYAO_LOG_LEVEL"] = original_log_level
            else:
                os.environ.pop("PYAO_LOG_LEVEL", None)

            # Restaurar paths originales
            if original_config_dir is not None:
                ConfigManager._config_dir = original_config_dir
            if original_config_file is not None:
                ConfigManager._config_file = original_config_file
