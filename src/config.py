"""Configuración centralizada del servidor.

Este módulo centraliza todas las configuraciones del servidor,
permitiendo sobrescribirlas mediante variables de entorno.

Para usar en producción, crea un archivo .env con las variables necesarias
o configura las variables de entorno directamente.
"""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ServerConfig:
    """Configuración del servidor TCP."""

    host: str
    port: int
    max_connections: int

    @classmethod
    def from_env(cls) -> ServerConfig:
        """Carga configuración desde variables de entorno.

        Returns:
            ServerConfig con valores de variables de entorno o defaults.
        """
        return cls(
            host=os.getenv("SERVER_HOST", "0.0.0.0"),
            port=int(os.getenv("SERVER_PORT", "7666")),
            max_connections=int(os.getenv("SERVER_MAX_CONNECTIONS", "1000")),
        )


@dataclass(frozen=True)
class RedisConfig:
    """Configuración de conexión a Redis."""

    host: str
    port: int
    db: int
    decode_responses: bool
    socket_timeout: float
    socket_connect_timeout: float

    @classmethod
    def from_env(cls) -> RedisConfig:
        """Carga configuración desde variables de entorno.

        Returns:
            RedisConfig con valores de variables de entorno o defaults.
        """
        return cls(
            host=os.getenv("REDIS_HOST", "localhost"),
            port=int(os.getenv("REDIS_PORT", "6379")),
            db=int(os.getenv("REDIS_DB", "0")),
            decode_responses=os.getenv("REDIS_DECODE_RESPONSES", "true").lower() == "true",
            socket_timeout=float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0")),
            socket_connect_timeout=float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0")),
        )


@dataclass(frozen=True)
class GameConfig:
    """Configuración de gameplay y límites del juego."""

    max_inventory_slots: int
    max_bank_slots: int
    max_party_members: int
    respawn_time_seconds: int
    max_level: int
    hp_per_con: int
    mana_per_int: int
    initial_gold: int
    initial_elu: int

    @classmethod
    def from_env(cls) -> GameConfig:
        """Carga configuración desde variables de entorno.

        Returns:
            GameConfig con valores de variables de entorno o defaults.
        """
        return cls(
            max_inventory_slots=int(os.getenv("GAME_MAX_INVENTORY_SLOTS", "25")),
            max_bank_slots=int(os.getenv("GAME_MAX_BANK_SLOTS", "40")),
            max_party_members=int(os.getenv("GAME_MAX_PARTY_MEMBERS", "6")),
            respawn_time_seconds=int(os.getenv("GAME_RESPAWN_TIME_SECONDS", "180")),
            max_level=int(os.getenv("GAME_MAX_LEVEL", "50")),
            hp_per_con=int(os.getenv("GAME_HP_PER_CON", "10")),
            mana_per_int=int(os.getenv("GAME_MANA_PER_INT", "10")),
            initial_gold=int(os.getenv("GAME_INITIAL_GOLD", "0")),
            initial_elu=int(os.getenv("GAME_INITIAL_ELU", "300")),
        )


@dataclass(frozen=True)
class HungerThirstConfig:
    """Configuración del sistema de hambre y sed."""

    enabled: bool
    interval_sed_seconds: int
    interval_hambre_seconds: int
    reduccion_agua: int
    reduccion_hambre: int

    @classmethod
    def from_env(cls) -> HungerThirstConfig:
        """Carga configuración desde variables de entorno.

        Returns:
            HungerThirstConfig con valores de variables de entorno o defaults.
        """
        return cls(
            enabled=os.getenv("HUNGER_THIRST_ENABLED", "true").lower() == "true",
            interval_sed_seconds=int(os.getenv("HUNGER_THIRST_INTERVAL_SED", "180")),
            interval_hambre_seconds=int(os.getenv("HUNGER_THIRST_INTERVAL_HAMBRE", "180")),
            reduccion_agua=int(os.getenv("HUNGER_THIRST_REDUCCION_AGUA", "10")),
            reduccion_hambre=int(os.getenv("HUNGER_THIRST_REDUCCION_HAMBRE", "10")),
        )


@dataclass(frozen=True)
class GoldDecayConfig:
    """Configuración del sistema de reducción de oro."""

    enabled: bool
    percentage: float
    interval_seconds: float

    @classmethod
    def from_env(cls) -> GoldDecayConfig:
        """Carga configuración desde variables de entorno.

        Returns:
            GoldDecayConfig con valores de variables de entorno o defaults.
        """
        return cls(
            enabled=os.getenv("GOLD_DECAY_ENABLED", "true").lower() == "true",
            percentage=float(os.getenv("GOLD_DECAY_PERCENTAGE", "1.0")),
            interval_seconds=float(os.getenv("GOLD_DECAY_INTERVAL_SECONDS", "60.0")),
        )


@dataclass(frozen=True)
class Config:
    """Configuración global del servidor."""

    server: ServerConfig
    redis: RedisConfig
    game: GameConfig
    hunger_thirst: HungerThirstConfig
    gold_decay: GoldDecayConfig

    @classmethod
    def from_env(cls) -> Config:
        """Carga toda la configuración desde variables de entorno.

        Returns:
            Config con todas las sub-configuraciones cargadas.
        """
        return cls(
            server=ServerConfig.from_env(),
            redis=RedisConfig.from_env(),
            game=GameConfig.from_env(),
            hunger_thirst=HungerThirstConfig.from_env(),
            gold_decay=GoldDecayConfig.from_env(),
        )


# Instancia global de configuración
# Se carga automáticamente al importar este módulo
config = Config.from_env()
