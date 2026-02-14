"""Tests para el nuevo sistema de configuración con Pydantic."""

import math
import os
import tempfile
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.config.game_config import (
    BankConfig,
    CharacterConfig,
    CombatConfig,
    GameConfig,
    HungerThirstConfig,
    InventoryConfig,
    ServerConfig,
    StaminaConfig,
    WorkConfig,
)


class TestGameConfig:
    """Tests para GameConfig."""

    def test_default_config(self) -> None:
        """Test que la configuración por defecto funciona."""
        config = GameConfig()
        assert config.server.port == 7666
        assert config.server.host == "0.0.0.0"
        assert math.isclose(config.game.combat.base_critical_chance, 0.15)

    def test_load_from_toml(self) -> None:
        """Test cargar configuración desde TOML."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            toml_content = b"""
[server]
host = "127.0.0.1"
port = 8080
max_connections = 500

[game]
max_players_per_map = 50

[game.combat]
base_critical_chance = 0.20
"""
            f.write(toml_content)
            f.flush()

            try:
                config = GameConfig.from_toml(f.name)
                assert config.server.host == "127.0.0.1"
                assert config.server.port == 8080
                assert config.server.max_connections == 500
                assert config.game.max_players_per_map == 50
                assert math.isclose(config.game.combat.base_critical_chance, 0.20)
            finally:
                Path(f.name).unlink()

    def test_validation_port_too_low(self) -> None:
        """Test que la validación rechaza puertos inválidos (muy bajos)."""
        with pytest.raises(ValidationError):
            ServerConfig(port=100)  # Menor que 1024

    def test_validation_port_too_high(self) -> None:
        """Test que la validación rechaza puertos inválidos (muy altos)."""
        with pytest.raises(ValidationError):
            ServerConfig(port=70000)  # Mayor que 65535

    def test_validation_probability_range(self) -> None:
        """Test que las probabilidades deben estar entre 0 y 1."""
        with pytest.raises(ValidationError):
            CombatConfig(base_critical_chance=1.5)  # Mayor que 1.0

        with pytest.raises(ValidationError):
            CombatConfig(base_critical_chance=-0.1)  # Menor que 0.0

    def test_get_method(self) -> None:
        """Test el método get() para compatibilidad."""
        config = GameConfig()
        assert config.get("server.port") == 7666
        assert math.isclose(config.get("game.combat.base_critical_chance"), 0.15)
        assert config.get("nonexistent.key", "default") == "default"

    def test_env_variables(self) -> None:
        """Test que las variables de entorno funcionan."""
        # Establecer variable de entorno
        os.environ["PYAO_SERVER__PORT"] = "9999"
        os.environ["PYAO_GAME__COMBAT__BASE_CRITICAL_CHANCE"] = "0.25"

        try:
            # Crear nueva instancia (carga variables de entorno)
            config = GameConfig()
            assert config.server.port == 9999
            assert math.isclose(config.game.combat.base_critical_chance, 0.25)
        finally:
            # Limpiar
            del os.environ["PYAO_SERVER__PORT"]
            del os.environ["PYAO_GAME__COMBAT__BASE_CRITICAL_CHANCE"]

    def test_nested_configs(self) -> None:
        """Test que las configuraciones anidadas funcionan."""
        config = GameConfig()
        assert isinstance(config.game.combat, CombatConfig)
        assert isinstance(config.game.work, WorkConfig)
        assert isinstance(config.game.stamina, StaminaConfig)
        assert isinstance(config.game.inventory, InventoryConfig)
        assert isinstance(config.game.bank, BankConfig)
        assert isinstance(config.game.character, CharacterConfig)
        assert isinstance(config.game.hunger_thirst, HungerThirstConfig)

    def test_to_dict(self) -> None:
        """Test que to_dict() funciona."""
        config = GameConfig()
        config_dict = config.to_dict()
        assert "server" in config_dict
        assert "game" in config_dict
        assert config_dict["server"]["port"] == 7666

    def test_reload(self) -> None:
        """Test que reload() funciona."""
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".toml", delete=False) as f:
            toml_content = b"""
[server]
port = 7777
"""
            f.write(toml_content)
            f.flush()

            try:
                config = GameConfig()
                original_port = config.server.port
                config.reload(f.name)
                assert config.server.port == 7777
                assert config.server.port != original_port
            finally:
                Path(f.name).unlink()
