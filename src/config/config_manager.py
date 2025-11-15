"""Sistema centralizado de configuración del servidor."""

import logging
import os
import tomllib
from pathlib import Path
from typing import Any, ClassVar, Self

logger = logging.getLogger(__name__)

# Tipo para valores de configuración
ConfigValue = str | int | float | bool | dict[str, Any] | None
ConfigDict = dict[str, ConfigValue]


class ConfigManager:
    """Gestor centralizado de configuración con soporte para archivos TOML."""

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

        self._load_config()

    def _load_config(self) -> None:
        """Carga la configuración desde archivo TOML."""
        try:
            # Crear directorio config si no existe
            self._config_dir.mkdir(exist_ok=True)

            # Cargar configuración base
            if self._config_file.exists():
                with Path(self._config_file).open("rb") as f:
                    ConfigManager._config = tomllib.load(f)
                logger.info("Configuración cargada desde %s", self._config_file)
            else:
                logger.warning("Archivo de configuración no encontrado: %s", self._config_file)
                self._config = self._get_default_config()  # type: ignore[misc]
                logger.info("Usando configuración por defecto")

            # Sobrescribir con variables de entorno
            self._load_env_overrides()

            # Validar configuración
            self._validate_config()

        except Exception:
            logger.exception("Error cargando configuración")
            self._config = self._get_default_config()  # type: ignore[misc]

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
        """Carga sobrescrituras de configuración desde variables de entorno."""
        env_mappings = {
            "PYAO_SERVER_HOST": ("server", "host"),
            "PYAO_SERVER_PORT": ("server", "port"),
            "PYAO_SERVER_MAX_CONNECTIONS": ("server", "max_connections"),
            "PYAO_REDIS_HOST": ("redis", "host"),
            "PYAO_REDIS_PORT": ("redis", "port"),
            "PYAO_REDIS_DB": ("redis", "db"),
            "PYAO_LOG_LEVEL": ("logging", "level"),
        }

        for env_var, (section, key) in env_mappings.items():
            value_str = os.getenv(env_var)
            if value_str is not None:
                # Convertir tipos según corresponda
                if key in {"port", "max_connections", "db"}:
                    value: ConfigValue = int(value_str)
                else:
                    value = value_str

                if section not in self._config:
                    self._config[section] = {}
                self._config[section][key] = value  # type: ignore[index]
                logger.info(
                    "Configuración sobrescrita desde %s: %s.%s = %s", env_var, section, key, value
                )

    def _validate_config(self) -> None:
        """Valida que la configuración sea correcta.

        Raises:
            ValueError: Si hay errores de validación en la configuración.
        """
        errors = []

        # Validar puerto
        port_value = self.get("server.port", 0)
        try:
            port = int(port_value) if isinstance(port_value, (int, str)) else 0
        except (ValueError, TypeError):
            port = 0
        if not (self.MIN_PORT <= port <= self.MAX_PORT):
            errors.append(
                f"Puerto inválido: {port}. Debe estar entre {self.MIN_PORT}-{self.MAX_PORT}"
            )

        # Validar valores positivos
        positive_keys = [
            "server.max_connections",
            "game.max_players_per_map",
            "game.combat.melee_range",
            "game.work.exp_per_level",
        ]

        for key in positive_keys:
            value_raw = self.get(key, 0)
            try:
                value_int = int(value_raw) if isinstance(value_raw, (int, str)) else 0
            except (ValueError, TypeError):
                value_int = 0
            if value_int <= 0:
                errors.append(f"Valor inválido para {key}: {value_int}. Debe ser > 0")

        # Validar probabilidades
        probability_keys = [
            "game.combat.base_critical_chance",
            "game.combat.base_dodge_chance",
        ]

        for key in probability_keys:
            value_raw = self.get(key, 0)
            try:
                value_float = float(value_raw) if isinstance(value_raw, (int, float, str)) else 0.0
            except (ValueError, TypeError):
                value_float = 0.0
            if not (0.0 <= value_float <= 1.0):
                errors.append(
                    f"Probabilidad inválida para {key}: {value_float}. Debe estar entre 0.0-1.0"
                )

        if errors:
            error_msg = "Errores de validación de configuración:\n" + "\n".join(
                f"- {error}" for error in errors
            )
            logger.error(error_msg)
            raise ValueError(error_msg)

        logger.info("Configuración validada correctamente")

    @staticmethod
    def _save_config() -> None:
        """Guarda la configuración actual al archivo TOML (no implementado)."""
        # El sistema es read-only para simplificar
        logger.debug("Guardado de configuración no implementado (modo read-only)")

    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue:
        """Obtiene un valor de configuración usando notación de puntos (section.key).

        Args:
            key: Clave de configuración (ej: "server.port")
            default: Valor por defecto si no se encuentra

        Returns:
            Valor de configuración o default
        """
        keys = key.split(".")
        value: ConfigValue = self._config

        try:
            for k in keys:
                if isinstance(value, dict):
                    value = value[k]
                else:
                    return default
        except (KeyError, TypeError):
            return default
        else:
            return value

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
        self._load_config()

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
