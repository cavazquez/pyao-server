"""Tests para el sistema de configuración centralizada."""

import os
import tempfile
import unittest
from pathlib import Path

from src.config.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    """Tests para ConfigManager."""

    def setUp(self) -> None:
        """Configura entorno de prueba."""
        # Crear directorio temporal
        self.temp_dir = Path(tempfile.mkdtemp())
        self.config_file = self.temp_dir / "test_server.toml"

        # Configurar variables de entorno para pruebas
        os.environ["PYAO_SERVER_PORT"] = "9999"
        os.environ["PYAO_LOG_LEVEL"] = "DEBUG"

        # Resetear singleton
        ConfigManager._instance = None
        ConfigManager._config = {}
        if hasattr(ConfigManager, "_initialized"):
            delattr(ConfigManager, "_initialized")

    def tearDown(self) -> None:
        """Limpia entorno de prueba."""
        # Limpiar variables de entorno
        for key in ["PYAO_SERVER_PORT", "PYAO_LOG_LEVEL"]:
            if key in os.environ:
                del os.environ[key]

        # Resetear singleton
        ConfigManager._instance = None
        ConfigManager._config = {}
        if hasattr(ConfigManager, "_initialized"):
            delattr(ConfigManager, "_initialized")

    def test_default_config_creation(self) -> None:
        """Test que se crea configuración por defecto cuando no existe archivo."""
        # Modificar el path del config manager para usar nuestro archivo temporal
        Path(__file__).parent.parent / "config"
        ConfigManager._config_dir = self.temp_dir
        ConfigManager._config_file = self.config_file

        # Crear nueva instancia
        config = ConfigManager()

        # Verificar valores por defecto
        assert config.get("server.port") == 9999  # Variable de entorno activa
        assert config.get("server.host") == "0.0.0.0"
        assert config.get("game.combat.melee_range") == 1
        assert config.get("game.work.exp_wood") == 10
        assert config.get("game.work.exp_per_level") == 100

        # Verificar que NO se creó el archivo (es read-only)
        assert not self.config_file.exists()

    def test_load_config_from_file(self) -> None:
        """Test que carga configuración desde archivo TOML existente."""
        # Usar el archivo de configuración real del proyecto
        config_file = Path(__file__).parent.parent / "config" / "server.toml"

        if config_file.exists():
            ConfigManager._config_dir = config_file.parent
            ConfigManager._config_file = config_file

            # Crear instancia y verificar valores
            config = ConfigManager()

            assert config.get("server.host") == "0.0.0.0"
            assert config.get("server.port") == 9999  # Variable de entorno activa
            assert config.get("game.combat.melee_range") == 1
            assert config.get("game.work.exp_wood") == 10
            assert config.get("game.work.exp_per_level") == 100
        else:
            self.skipTest("Archivo config/server.toml no encontrado")

    def test_environment_overrides(self) -> None:
        """Test que las variables de entorno sobrescriben la configuración."""
        # Usar el archivo de configuración real
        config_file = Path(__file__).parent.parent / "config" / "server.toml"

        if config_file.exists():
            ConfigManager._config_dir = config_file.parent
            ConfigManager._config_file = config_file

            # Crear instancia
            config = ConfigManager()

            # Verificar que las variables de entorno sobrescriben
            assert config.get("server.port") == 9999  # Desde env
            assert config.get("logging.level") == "DEBUG"  # Desde env
        else:
            self.skipTest("Archivo config/server.toml no encontrado")

    def test_get_with_default(self) -> None:
        """Test método get con valor por defecto."""
        ConfigManager._config_dir = self.temp_dir
        ConfigManager._config_file = self.config_file

        config = ConfigManager()

        # Valor existente
        assert config.get("server.port") == 9999  # Variable de entorno activa

        # Valor no existente con default
        assert config.get("nonexistent.key", "default_value") == "default_value"
        assert config.get("missing.number", 42) == 42

        # Valor no existente sin default
        assert config.get("nonexistent.key") is None

    def test_set_and_reload(self) -> None:
        """Test métodos set y reload."""
        ConfigManager._config_dir = self.temp_dir
        ConfigManager._config_file = self.config_file

        config = ConfigManager()

        # Verificar valor inicial
        assert config.get("server.port") == 9999  # Variable de entorno activa

        # Modificar valor
        config.set("server.port", 8888)
        assert config.get("server.port") == 8888

        # Crear nuevo valor
        config.set("new.section.value", "test")
        assert config.get("new.section.value") == "test"

        # Recargar y verificar que vuelve a las variables de entorno
        config.reload()
        assert config.get("server.port") == 9999  # Variable de entorno sobrescribe
        # Los nuevos valores se pierden porque _save_config es no-op
        assert config.get("new.section.value") is None

    def test_get_section(self) -> None:
        """Test método get_section."""
        ConfigManager._config_dir = self.temp_dir
        ConfigManager._config_file = self.config_file

        config = ConfigManager()

        server_section = config.get_section("server")
        assert isinstance(server_section, dict)
        assert "host" in server_section
        assert "port" in server_section

        # Sección inexistente
        empty_section = config.get_section("nonexistent")
        assert empty_section == {}

    def test_get_all(self) -> None:
        """Test método get_all."""
        ConfigManager._config_dir = self.temp_dir
        ConfigManager._config_file = self.config_file

        config = ConfigManager()

        all_config = config.get_all()
        assert isinstance(all_config, dict)
        assert "server" in all_config
        assert "game" in all_config
        assert "logging" in all_config
        assert "redis" in all_config

        # Verificar que es una copia
        all_config["test"] = "value"
        assert config.get("test") is None

    def test_singleton_pattern(self) -> None:
        """Test que ConfigManager implementa singleton correctamente."""
        ConfigManager._config_dir = self.temp_dir
        ConfigManager._config_file = self.config_file

        config1 = ConfigManager()
        config2 = ConfigManager()

        # Deben ser la misma instancia
        assert config1 is config2

        # Modificar en uno debe afectar al otro
        config1.set("test.value", "from_config1")
        assert config2.get("test.value") == "from_config1"

    def test_validation_errors(self) -> None:
        """Test validación de configuración con errores."""
        # Guardar variables de entorno originales
        original_env = {}
        for key in ["PYAO_SERVER_PORT", "PYAO_LOG_LEVEL", "PYAO_REDIS_HOST", "PYAO_REDIS_PORT"]:
            original_env[key] = os.environ.get(key)
            if key in os.environ:
                del os.environ[key]

        try:
            # Crear archivo de configuración inválido temporalmente
            invalid_config_file = self.temp_dir / "invalid_server.toml"
            invalid_config_file.write_text("""
[server]
port = 100  # Puerto inválido (< 1024)

[game.combat]
base_critical_chance = 1.5  # Probabilidad inválida (> 1.0)
melee_range = -1  # Rango inválido (< 0)
""")

            # Usar archivo inválido
            ConfigManager._config_dir = self.temp_dir
            ConfigManager._config_file = invalid_config_file

            # Resetear singleton completamente para forzar validación
            ConfigManager._instance = None
            ConfigManager._initialized = False
            # No limpiar _config para que cargue el archivo inválido

            # El ConfigManager debe manejar el error y usar defaults
            # Verificamos que se creó correctamente (con defaults)
            config = ConfigManager()

            # Verificar que usa los valores por defecto, no los inválidos
            assert config.get("server.port") == 7666  # Default, no 100
            assert config.get("game.combat.base_critical_chance") == 0.15  # Default, no 1.5
            assert config.get("game.combat.melee_range") == 1  # Default, no -1

        finally:
            # Restaurar variables de entorno
            for key, value in original_env.items():
                if value is not None:
                    os.environ[key] = value
                elif key in os.environ:
                    del os.environ[key]


if __name__ == "__main__":
    unittest.main()
