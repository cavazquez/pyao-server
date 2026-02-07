"""Sistema centralizado de configuración del servidor.

Este módulo mantiene compatibilidad con el sistema anterior mientras
migra gradualmente al nuevo sistema basado en Pydantic.
"""

import logging
import os
from pathlib import Path
from typing import Any, ClassVar, Self

from src.config.game_config import GameConfig

logger = logging.getLogger(__name__)

# Tipo para valores de configuración
ConfigValue = str | int | float | bool | dict[str, Any] | None
ConfigDict = dict[str, ConfigValue]


class ConfigManager:
    """Gestor centralizado de configuración con soporte para archivos TOML.

    Esta clase mantiene compatibilidad con el código existente mientras
    usa internamente el nuevo sistema basado en Pydantic para validación estricta.

    Nota: Se recomienda migrar gradualmente a usar GameConfig directamente
    para mejor validación y soporte de variables de entorno.
    """

    _instance: ConfigManager | None = None
    _config: ClassVar[ConfigDict] = {}

    # Constantes de validación
    MIN_PORT = 1024
    MAX_PORT = 65535

    def __new__(cls) -> Self:
        """Singleton pattern para asegurar una única instancia."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance  # type: ignore[return-value]

    def __init__(self) -> None:
        """Inicializa el gestor de configuración."""
        if getattr(self, "_initialized", False):
            return

        self._initialized = True

        # Usar paths configurados o defaults
        if not hasattr(self, "_config_dir"):
            self._config_dir = Path(__file__).parent.parent.parent / "config"
        if not hasattr(self, "_config_file"):
            self._config_file = self._config_dir / "server.toml"

        # Instancia de GameConfig (no es ClassVar)
        self._game_config: GameConfig | None = None

        # Cargar usando nuevo sistema Pydantic
        self._load_config_with_pydantic()

        # Mantener _config para compatibilidad
        self._sync_to_legacy_dict()

    def _load_config_with_pydantic(self) -> None:
        """Carga la configuración usando el nuevo sistema Pydantic."""
        try:
            # Crear directorio config si no existe
            self._config_dir.mkdir(exist_ok=True)

            # Mapear variables de entorno antiguas a nuevas (compatibilidad)
            # Debe hacerse ANTES de crear GameConfig
            ConfigManager._map_legacy_env_vars()

            # Cargar usando GameConfig (con validación Pydantic)
            # Las variables de entorno se cargan automáticamente por Pydantic Settings
            if self._config_file.exists():
                # Cargar desde TOML
                # Nota: Pydantic Settings carga variables de entorno automáticamente
                # y las sobrescribe sobre los valores del TOML cuando se crea la instancia
                self._game_config = GameConfig.from_toml(self._config_file)
                logger.info(
                    "Configuración cargada desde %s (con validación Pydantic)", self._config_file
                )
            else:
                logger.warning("Archivo de configuración no encontrado: %s", self._config_file)
                # Crear instancia que carga variables de entorno automáticamente
                self._game_config = GameConfig()  # Usar defaults + env vars
                logger.info("Usando configuración por defecto (con validación Pydantic)")

        except Exception:
            logger.exception("Error cargando configuración con Pydantic, usando defaults")
            # En caso de error, intentar crear con defaults
            try:
                self._map_legacy_env_vars()
                self._game_config = GameConfig()
            except Exception:
                logger.exception("Error crítico cargando configuración")
                # Último recurso: crear sin validación
                self._game_config = None

    @staticmethod
    def _map_legacy_env_vars() -> None:
        """Mapea variables de entorno antiguas a nuevas para compatibilidad.

        Convierte PYAO_SERVER_PORT -> PYAO_SERVER__PORT
        """
        legacy_mappings = {
            "PYAO_SERVER_HOST": "PYAO_SERVER__HOST",
            "PYAO_SERVER_PORT": "PYAO_SERVER__PORT",
            "PYAO_SERVER_MAX_CONNECTIONS": "PYAO_SERVER__MAX_CONNECTIONS",
            "PYAO_REDIS_HOST": "PYAO_REDIS__HOST",
            "PYAO_REDIS_PORT": "PYAO_REDIS__PORT",
            "PYAO_REDIS_DB": "PYAO_REDIS__DB",
            "PYAO_LOG_LEVEL": "PYAO_LOGGING__LEVEL",
        }

        for legacy_key, new_key in legacy_mappings.items():
            if legacy_key in os.environ and new_key not in os.environ:
                os.environ[new_key] = os.environ[legacy_key]
                logger.debug("Mapeada variable de entorno: %s -> %s", legacy_key, new_key)

    def _sync_to_legacy_dict(self) -> None:
        """Sincroniza GameConfig a _config para compatibilidad."""
        if self._game_config is None:
            ConfigManager._config = self._get_default_config()
            return

        # Convertir GameConfig a estructura de dict anidada
        ConfigManager._config = {
            "server": {
                "host": self._game_config.server.host,
                "port": self._game_config.server.port,
                "max_connections": self._game_config.server.max_connections,
                "buffer_size": self._game_config.server.buffer_size,
            },
            "game": {
                "max_players_per_map": self._game_config.game.max_players_per_map,
                "respawn_check_interval": self._game_config.game.respawn_check_interval,
                "npc_respawn_base_time": self._game_config.game.npc_respawn_base_time,
                "npc_respawn_random_variance": self._game_config.game.npc_respawn_random_variance,
                "combat": {
                    "melee_range": self._game_config.game.combat.melee_range,
                    "base_critical_chance": self._game_config.game.combat.base_critical_chance,
                    "base_dodge_chance": self._game_config.game.combat.base_dodge_chance,
                    "defense_per_level": self._game_config.game.combat.defense_per_level,
                    "armor_reduction": self._game_config.game.combat.armor_reduction,
                    "critical_damage_multiplier": (
                        self._game_config.game.combat.critical_damage_multiplier
                    ),
                    "critical_agi_modifier": self._game_config.game.combat.critical_agi_modifier,
                    "dodge_agi_modifier": self._game_config.game.combat.dodge_agi_modifier,
                    "max_critical_chance": self._game_config.game.combat.max_critical_chance,
                    "max_dodge_chance": self._game_config.game.combat.max_dodge_chance,
                    "base_agility": self._game_config.game.combat.base_agility,
                },
                "work": {
                    "exp_wood": self._game_config.game.work.exp_wood,
                    "exp_mineral": self._game_config.game.work.exp_mineral,
                    "exp_fish": self._game_config.game.work.exp_fish,
                    "exp_per_level": self._game_config.game.work.exp_per_level,
                    "max_work_distance": self._game_config.game.work.max_work_distance,
                },
                "stamina": {
                    "max_stamina": self._game_config.game.stamina.max_stamina,
                    "stamina_regen_rate": self._game_config.game.stamina.stamina_regen_rate,
                    "stamina_drain_rate": self._game_config.game.stamina.stamina_drain_rate,
                    "cost_walk": self._game_config.game.stamina.cost_walk,
                    "cost_attack": self._game_config.game.stamina.cost_attack,
                    "cost_spell": self._game_config.game.stamina.cost_spell,
                    "cost_work": self._game_config.game.stamina.cost_work,
                    "regen_tick": self._game_config.game.stamina.regen_tick,
                    "regen_resting": self._game_config.game.stamina.regen_resting,
                },
                "hunger_thirst": {
                    "enabled": self._game_config.game.hunger_thirst.enabled,
                    "interval_sed": self._game_config.game.hunger_thirst.interval_sed,
                    "interval_hambre": self._game_config.game.hunger_thirst.interval_hambre,
                    "reduccion_agua": self._game_config.game.hunger_thirst.reduccion_agua,
                    "reduccion_hambre": self._game_config.game.hunger_thirst.reduccion_hambre,
                },
                "gold_decay": {
                    "enabled": self._game_config.game.gold_decay.enabled,
                    "percentage": self._game_config.game.gold_decay.percentage,
                    "interval_seconds": self._game_config.game.gold_decay.interval_seconds,
                },
                "inventory": {
                    "max_slots": self._game_config.game.inventory.max_slots,
                },
                "bank": {
                    "max_slots": self._game_config.game.bank.max_slots,
                },
                "character": {
                    "hp_per_con": self._game_config.game.character.hp_per_con,
                    "mana_per_int": self._game_config.game.character.mana_per_int,
                    "initial_gold": self._game_config.game.character.initial_gold,
                    "initial_elu": self._game_config.game.character.initial_elu,
                    "elu_exponent": self._game_config.game.character.elu_exponent,
                },
            },
            "logging": {
                "level": self._game_config.logging.level,
                "format": self._game_config.logging.format,
                "file": self._game_config.logging.file,
            },
            "redis": {
                "host": self._game_config.redis.host,
                "port": self._game_config.redis.port,
                "db": self._game_config.redis.db,
                "max_connections": self._game_config.redis.max_connections,
            },
        }

    @staticmethod
    def _get_default_config() -> ConfigDict:
        """Retorna la configuración por defecto.

        Returns:
            Diccionario con configuración por defecto.
        """
        return {
            "server": {
                "host": "0.0.0.0",
                "port": 7666,
                "max_connections": 1000,
                "buffer_size": 4096,
            },
            "game": {
                "max_players_per_map": 100,
                "respawn_check_interval": 5.0,
                "npc_respawn_base_time": 30.0,
                "npc_respawn_random_variance": 15.0,
                "combat": {
                    "melee_range": 1,
                    "base_critical_chance": 0.15,
                    "base_dodge_chance": 0.05,
                    "defense_per_level": 0.1,
                    "armor_reduction": 0.1,
                    "critical_damage_multiplier": 2.0,
                    "critical_agi_modifier": 0.005,
                    "dodge_agi_modifier": 0.007,
                    "max_critical_chance": 0.50,
                    "max_dodge_chance": 0.40,
                    "base_agility": 10,
                },
                "work": {
                    "exp_wood": 10,
                    "exp_mineral": 15,
                    "exp_fish": 12,
                    "exp_per_level": 100,
                    "max_work_distance": 1,
                },
                "stamina": {
                    "max_stamina": 100,
                    "stamina_regen_rate": 1.0,
                    "stamina_drain_rate": 2.0,
                    "cost_walk": 1,
                    "cost_attack": 2,
                    "cost_spell": 3,
                    "cost_work": 5,
                    "regen_tick": 2,
                    "regen_resting": 5,
                },
                "effects": {
                    "hunger_thirst": {
                        "enabled": True,
                        "interval_sed": 180,
                        "interval_hambre": 180,
                        "reduccion_agua": 10,
                        "reduccion_hambre": 10,
                    },
                    "gold_decay": {
                        "enabled": True,
                        "percentage": 1.0,
                        "interval_seconds": 60.0,
                    },
                },
                "inventory": {
                    "max_slots": 30,
                },
                "bank": {
                    "max_slots": 40,
                },
                "character": {
                    "hp_per_con": 10,
                    "mana_per_int": 10,
                    "initial_gold": 0,
                    "initial_elu": 300,
                    "elu_exponent": 1.8,  # Exponente para cálculo de ELU por nivel
                },
            },
            "logging": {
                "level": "INFO",
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "file": "logs/server.log",
            },
            "redis": {"host": "localhost", "port": 6379, "db": 0, "max_connections": 20},
        }

    def _load_env_overrides(self) -> None:
        """Carga sobrescrituras de configuración desde variables de entorno.

        Nota: Con el nuevo sistema Pydantic, las variables de entorno se cargan
        automáticamente. Este método se mantiene para compatibilidad pero ya no
        es necesario llamarlo explícitamente.
        """
        # Las variables de entorno ahora se cargan automáticamente por Pydantic
        # Este método se mantiene para compatibilidad pero no hace nada
        # porque GameConfig ya las carga automáticamente

    def _validate_config(self) -> None:
        """Valida que la configuración sea correcta.

        Nota: Con el nuevo sistema Pydantic, la validación se hace automáticamente
        al cargar la configuración. Este método se mantiene para compatibilidad.

        Raises:
            ValueError: Si hay errores de validación en la configuración.
        """
        # La validación ahora se hace automáticamente por Pydantic al crear GameConfig
        # Si llegamos aquí, la configuración ya está validada
        if self._game_config is None:
            msg = "Configuración no inicializada"
            raise ValueError(msg)

        logger.info("Configuración validada correctamente (por Pydantic)")

    @staticmethod
    def _save_config() -> None:
        """Guarda la configuración actual al archivo TOML (no implementado)."""
        # El sistema es read-only para simplificar
        logger.debug("Guardado de configuración no implementado (modo read-only)")

    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue:
        """Obtiene un valor de configuración usando notación de puntos (section.key).

        Usa el nuevo sistema Pydantic si está disponible, sino usa el dict legacy.
        Si el valor fue modificado con set(), usa el dict legacy primero.

        Args:
            key: Clave de configuración (ej: "server.port")
            default: Valor por defecto si no se encuentra

        Returns:
            Valor de configuración o default
        """
        # Primero verificar si el valor fue modificado en _config (set())
        # Esto tiene prioridad sobre GameConfig
        keys = key.split(".")
        value: ConfigValue = self._config

        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    break
            else:
                # Si encontramos el valor en _config y no es el default, usarlo
                # (puede haber sido modificado con set())
                if value is not None:
                    return value
        except KeyError, TypeError:
            pass

        # Si no está en _config o es None, usar GameConfig
        if self._game_config is not None:
            game_value = self._game_config.get(key, default)
            if game_value is not None:
                return game_value

        return default

    def set(self, key: str, value: ConfigValue) -> None:
        """Establece un valor de configuración usando notación de puntos.

        Args:
            key: Clave de configuración (ej: "server.port")
            value: Nuevo valor
        """
        keys = key.split(".")
        config: ConfigDict = self._config

        # Navegar hasta el penúltimo nivel
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            # Type checker: config[k] debe ser un dict
            current_value = config[k]
            if isinstance(current_value, dict):
                config = current_value
            else:
                config[k] = {}
                config = config[k]  # type: ignore[assignment]

        # Establecer el valor
        config[keys[-1]] = value
        logger.info("Configuración actualizada: %s = %s", key, value)

    def reload(self) -> None:
        """Recarga la configuración desde archivo."""
        logger.info("Recargando configuración...")
        self._load_config_with_pydantic()
        self._sync_to_legacy_dict()

    def get_section(self, section: str) -> ConfigDict:
        """Obtiene una sección completa de configuración.

        Args:
            section: Nombre de la sección

        Returns:
            Diccionario con la sección de configuración
        """
        section_data = self._config.get(section, {})
        return section_data if isinstance(section_data, dict) else {}

    def get_all(self) -> ConfigDict:
        """Retorna toda la configuración.

        Returns:
            Copia de toda la configuración.
        """
        return self._config.copy()

    @staticmethod
    def as_int(value: ConfigValue, default: int = 0) -> int:
        """Convierte un valor de configuración a int de forma segura.

        Args:
            value: Valor a convertir
            default: Valor por defecto si no se puede convertir

        Returns:
            Valor convertido o default
        """
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        if isinstance(value, float):
            return int(value)
        return default

    @staticmethod
    def as_float(value: ConfigValue, default: float = 0.0) -> float:
        """Convierte un valor de configuración a float de forma segura.

        Args:
            value: Valor a convertir
            default: Valor por defecto si no se puede convertir

        Returns:
            Valor convertido o default
        """
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        return default


# Instancia global del gestor de configuración
config_manager = ConfigManager()
