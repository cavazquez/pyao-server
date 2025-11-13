"""Tests para el sistema de configuración."""

import os
from unittest.mock import patch

import pytest

from src.config import (
    Config,
    GameConfig,
    GoldDecayConfig,
    HungerThirstConfig,
    RedisConfig,
    ServerConfig,
)


class TestServerConfig:
    """Tests para ServerConfig."""

    def test_from_env_defaults(self) -> None:
        """Verifica que ServerConfig use valores por defecto."""
        with patch.dict(os.environ, {}, clear=True):
            config = ServerConfig.from_env()

            assert config.host == "0.0.0.0"
            assert config.port == 7666
            assert config.max_connections == 1000

    def test_from_env_custom_values(self) -> None:
        """Verifica que ServerConfig use variables de entorno."""
        with patch.dict(
            os.environ,
            {
                "SERVER_HOST": "127.0.0.1",
                "SERVER_PORT": "8080",
                "SERVER_MAX_CONNECTIONS": "500",
            },
        ):
            config = ServerConfig.from_env()

            assert config.host == "127.0.0.1"
            assert config.port == 8080
            assert config.max_connections == 500

    def test_immutable(self) -> None:
        """Verifica que ServerConfig sea inmutable."""
        config = ServerConfig.from_env()

        with pytest.raises(AttributeError):
            config.host = "new_host"  # type: ignore[misc]


class TestRedisConfig:
    """Tests para RedisConfig."""

    def test_from_env_defaults(self) -> None:
        """Verifica que RedisConfig use valores por defecto."""
        with patch.dict(os.environ, {}, clear=True):
            config = RedisConfig.from_env()

            assert config.host == "localhost"
            assert config.port == 6379
            assert config.db == 0
            assert config.decode_responses is True
            assert config.socket_timeout == 5.0
            assert config.socket_connect_timeout == 5.0

    def test_from_env_custom_values(self) -> None:
        """Verifica que RedisConfig use variables de entorno."""
        with patch.dict(
            os.environ,
            {
                "REDIS_HOST": "redis.example.com",
                "REDIS_PORT": "6380",
                "REDIS_DB": "1",
                "REDIS_DECODE_RESPONSES": "false",
                "REDIS_SOCKET_TIMEOUT": "10.0",
                "REDIS_SOCKET_CONNECT_TIMEOUT": "3.0",
            },
        ):
            config = RedisConfig.from_env()

            assert config.host == "redis.example.com"
            assert config.port == 6380
            assert config.db == 1
            assert config.decode_responses is False
            assert config.socket_timeout == 10.0
            assert config.socket_connect_timeout == 3.0


class TestGameConfig:
    """Tests para GameConfig."""

    def test_from_env_defaults(self) -> None:
        """Verifica que GameConfig use valores por defecto."""
        with patch.dict(os.environ, {}, clear=True):
            config = GameConfig.from_env()

            assert config.max_inventory_slots == 25
            assert config.max_bank_slots == 40
            assert config.max_party_members == 6
            assert config.respawn_time_seconds == 180
            assert config.max_level == 50

    def test_from_env_custom_values(self) -> None:
        """Verifica que GameConfig use variables de entorno."""
        with patch.dict(
            os.environ,
            {
                "GAME_MAX_INVENTORY_SLOTS": "30",
                "GAME_MAX_BANK_SLOTS": "50",
                "GAME_MAX_PARTY_MEMBERS": "8",
                "GAME_RESPAWN_TIME_SECONDS": "300",
                "GAME_MAX_LEVEL": "100",
            },
        ):
            config = GameConfig.from_env()

            assert config.max_inventory_slots == 30
            assert config.max_bank_slots == 50
            assert config.max_party_members == 8
            assert config.respawn_time_seconds == 300
            assert config.max_level == 100


class TestHungerThirstConfig:
    """Tests para HungerThirstConfig."""

    def test_from_env_defaults(self) -> None:
        """Verifica que HungerThirstConfig use valores por defecto."""
        with patch.dict(os.environ, {}, clear=True):
            config = HungerThirstConfig.from_env()

            assert config.enabled is True
            assert config.interval_sed_seconds == 180
            assert config.interval_hambre_seconds == 180
            assert config.reduccion_agua == 10
            assert config.reduccion_hambre == 10

    def test_from_env_custom_values(self) -> None:
        """Verifica que HungerThirstConfig use variables de entorno."""
        with patch.dict(
            os.environ,
            {
                "HUNGER_THIRST_ENABLED": "false",
                "HUNGER_THIRST_INTERVAL_SED": "300",
                "HUNGER_THIRST_INTERVAL_HAMBRE": "240",
                "HUNGER_THIRST_REDUCCION_AGUA": "5",
                "HUNGER_THIRST_REDUCCION_HAMBRE": "8",
            },
        ):
            config = HungerThirstConfig.from_env()

            assert config.enabled is False
            assert config.interval_sed_seconds == 300
            assert config.interval_hambre_seconds == 240
            assert config.reduccion_agua == 5
            assert config.reduccion_hambre == 8


class TestGoldDecayConfig:
    """Tests para GoldDecayConfig."""

    def test_from_env_defaults(self) -> None:
        """Verifica que GoldDecayConfig use valores por defecto."""
        with patch.dict(os.environ, {}, clear=True):
            config = GoldDecayConfig.from_env()

            assert config.enabled is True
            assert config.percentage == 1.0
            assert config.interval_seconds == 60.0

    def test_from_env_custom_values(self) -> None:
        """Verifica que GoldDecayConfig use variables de entorno."""
        with patch.dict(
            os.environ,
            {
                "GOLD_DECAY_ENABLED": "false",
                "GOLD_DECAY_PERCENTAGE": "2.5",
                "GOLD_DECAY_INTERVAL_SECONDS": "120.0",
            },
        ):
            config = GoldDecayConfig.from_env()

            assert config.enabled is False
            assert config.percentage == 2.5
            assert config.interval_seconds == 120.0


class TestConfig:
    """Tests para Config global."""

    def test_from_env_creates_all_configs(self) -> None:
        """Verifica que Config.from_env() cree todas las sub-configuraciones."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()

            assert isinstance(config.server, ServerConfig)
            assert isinstance(config.redis, RedisConfig)
            assert isinstance(config.game, GameConfig)
            assert isinstance(config.hunger_thirst, HungerThirstConfig)
            assert isinstance(config.gold_decay, GoldDecayConfig)

    def test_config_is_immutable(self) -> None:
        """Verifica que Config sea inmutable."""
        config = Config.from_env()

        with pytest.raises(AttributeError):
            config.server = ServerConfig.from_env()  # type: ignore[misc]
