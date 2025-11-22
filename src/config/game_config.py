"""Configuración del juego con validación estricta usando Pydantic."""

import logging
import tomllib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Tipo para valores de configuración (compatible con ConfigManager)
ConfigValue = str | int | float | bool | dict[str, Any] | None


class ServerConfig(BaseModel):
    """Configuración del servidor."""

    host: str = Field(default="0.0.0.0", description="Dirección del servidor")
    port: int = Field(default=7666, ge=1024, le=65535, description="Puerto del servidor")
    max_connections: int = Field(default=1000, ge=1, description="Máximo de conexiones simultáneas")
    buffer_size: int = Field(default=4096, ge=1024, description="Tamaño del buffer de red")


class CombatConfig(BaseModel):
    """Configuración de combate."""

    melee_range: int = Field(default=1, ge=1, le=10, description="Rango de combate cuerpo a cuerpo")
    base_critical_chance: float = Field(
        default=0.15, ge=0.0, le=1.0, description="Probabilidad base de golpe crítico"
    )
    base_dodge_chance: float = Field(
        default=0.05, ge=0.0, le=1.0, description="Probabilidad base de esquivar"
    )
    defense_per_level: float = Field(default=0.1, ge=0.0, description="Defensa adicional por nivel")
    armor_reduction: float = Field(
        default=0.1, ge=0.0, le=1.0, description="Reducción de daño por armadura"
    )
    critical_damage_multiplier: float = Field(
        default=2.0, ge=1.0, description="Multiplicador de daño crítico"
    )
    critical_agi_modifier: float = Field(
        default=0.005, ge=0.0, description="Modificador de crítico por punto de AGI"
    )
    dodge_agi_modifier: float = Field(
        default=0.007, ge=0.0, description="Modificador de esquivar por punto de AGI"
    )
    max_critical_chance: float = Field(
        default=0.50, ge=0.0, le=1.0, description="Probabilidad máxima de crítico"
    )
    max_dodge_chance: float = Field(
        default=0.40, ge=0.0, le=1.0, description="Probabilidad máxima de esquivar"
    )
    base_agility: int = Field(default=10, ge=1, description="Agilidad base de referencia")


class WorkConfig(BaseModel):
    """Configuración de trabajo."""

    exp_wood: int = Field(default=10, ge=1, description="Experiencia por talar madera")
    exp_mineral: int = Field(default=15, ge=1, description="Experiencia por minar")
    exp_fish: int = Field(default=12, ge=1, description="Experiencia por pescar")
    exp_per_level: int = Field(default=100, ge=1, description="Experiencia base por nivel")
    max_work_distance: int = Field(
        default=1, ge=1, le=10, description="Distancia máxima para trabajar"
    )


class StaminaConfig(BaseModel):
    """Configuración de stamina/energía."""

    max_stamina: int = Field(default=100, ge=1, description="Stamina máxima")
    stamina_regen_rate: float = Field(
        default=1.0, ge=0.0, description="Tasa de regeneración de stamina"
    )
    stamina_drain_rate: float = Field(default=2.0, ge=0.0, description="Tasa de consumo de stamina")
    cost_walk: int = Field(default=1, ge=0, description="Costo de stamina por caminar")
    cost_attack: int = Field(default=2, ge=0, description="Costo de stamina por atacar")
    cost_spell: int = Field(default=3, ge=0, description="Costo de stamina por hechizo")
    cost_work: int = Field(default=5, ge=0, description="Costo de stamina por trabajar")
    regen_tick: int = Field(default=2, ge=0, description="Stamina regenerada por tick")
    regen_resting: int = Field(
        default=5, ge=0, description="Stamina regenerada si está descansando"
    )


class HungerThirstConfig(BaseModel):
    """Configuración de hambre y sed."""

    enabled: bool = Field(default=True, description="Habilitar sistema de hambre/sed")
    interval_sed: int = Field(
        default=180, ge=1, description="Intervalo en segundos entre ticks de sed"
    )
    interval_hambre: int = Field(
        default=180, ge=1, description="Intervalo en segundos entre ticks de hambre"
    )
    reduccion_agua: int = Field(default=10, ge=0, description="Puntos de sed reducidos por tick")
    reduccion_hambre: int = Field(
        default=10, ge=0, description="Puntos de hambre reducidos por tick"
    )


class GoldDecayConfig(BaseModel):
    """Configuración de decaimiento de oro."""

    enabled: bool = Field(default=True, description="Habilitar decaimiento de oro")
    percentage: float = Field(
        default=1.0, ge=0.0, le=100.0, description="Porcentaje de oro a perder"
    )
    interval_seconds: float = Field(default=60.0, ge=1.0, description="Intervalo en segundos")


class InventoryConfig(BaseModel):
    """Configuración de inventario."""

    max_slots: int = Field(default=30, ge=1, le=100, description="Máximo de slots de inventario")


class BankConfig(BaseModel):
    """Configuración de bóveda bancaria."""

    max_slots: int = Field(default=40, ge=1, le=200, description="Máximo de slots de bóveda")


class CharacterConfig(BaseModel):
    """Configuración de personajes."""

    hp_per_con: int = Field(default=10, ge=1, description="HP adicional por punto de constitución")
    mana_per_int: int = Field(
        default=10, ge=1, description="Mana adicional por punto de inteligencia"
    )
    initial_gold: int = Field(default=0, ge=0, description="Oro inicial de nuevos personajes")
    initial_elu: int = Field(default=300, ge=0, description="ELU inicial de nuevos personajes")
    elu_exponent: float = Field(
        default=1.8, ge=1.0, le=3.0, description="Exponente para cálculo de ELU por nivel"
    )


class GameConfigSection(BaseModel):
    """Sección de configuración del juego."""

    max_players_per_map: int = Field(default=100, ge=1, description="Máximo de jugadores por mapa")
    respawn_check_interval: float = Field(
        default=5.0, ge=0.1, description="Intervalo de verificación de respawns"
    )
    npc_respawn_base_time: float = Field(
        default=30.0, ge=1.0, description="Tiempo base de respawn de NPCs"
    )
    npc_respawn_random_variance: float = Field(
        default=15.0, ge=0.0, description="Varianza aleatoria en respawns"
    )
    combat: CombatConfig = Field(default_factory=CombatConfig)
    work: WorkConfig = Field(default_factory=WorkConfig)
    stamina: StaminaConfig = Field(default_factory=StaminaConfig)
    hunger_thirst: HungerThirstConfig = Field(default_factory=HungerThirstConfig)
    gold_decay: GoldDecayConfig = Field(default_factory=GoldDecayConfig)
    inventory: InventoryConfig = Field(default_factory=InventoryConfig)
    bank: BankConfig = Field(default_factory=BankConfig)
    character: CharacterConfig = Field(default_factory=CharacterConfig)


class LoggingConfig(BaseModel):
    """Configuración de logging."""

    level: str = Field(
        default="INFO",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
        description="Nivel de logging",
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Formato de logs",
    )
    file: str = Field(default="logs/server.log", description="Archivo de logs")


class RedisConfig(BaseModel):
    """Configuración de Redis."""

    host: str = Field(default="localhost", description="Host de Redis")
    port: int = Field(default=6379, ge=1, le=65535, description="Puerto de Redis")
    db: int = Field(default=0, ge=0, description="Base de datos de Redis")
    max_connections: int = Field(default=20, ge=1, description="Máximo de conexiones a Redis")


class GameConfig(BaseSettings):
    """Configuración completa del juego con validación estricta.

    Esta clase usa Pydantic para validación automática de tipos y valores.
    Soporta carga desde archivo TOML y variables de entorno.

    Variables de entorno:
        Todas las configuraciones pueden ser sobrescritas con variables de entorno
        usando el prefijo PYAO_ y notación de puntos convertida a guiones bajos.

        Ejemplos:
            PYAO_SERVER_HOST=0.0.0.0
            PYAO_SERVER_PORT=7666
            PYAO_GAME_COMBAT_BASE_CRITICAL_CHANCE=0.2
            PYAO_GAME_INVENTORY_MAX_SLOTS=40
    """

    model_config = SettingsConfigDict(
        env_prefix="PYAO_",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",  # Para anidar: PYAO_GAME__COMBAT__BASE_CRITICAL_CHANCE
        case_sensitive=False,
        extra="ignore",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    game: GameConfigSection = Field(default_factory=GameConfigSection)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)

    @classmethod
    def from_toml(cls, toml_path: Path | str) -> GameConfig:
        """Carga configuración desde archivo TOML.

        Args:
            toml_path: Ruta al archivo TOML.

        Returns:
            Instancia de GameConfig cargada desde TOML.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si el archivo TOML es inválido.
        """
        path = Path(toml_path)
        if not path.exists():
            msg = f"Archivo de configuración no encontrado: {path}"
            raise FileNotFoundError(msg)

        try:
            with path.open("rb") as f:
                data = tomllib.load(f)
        except Exception as e:
            msg = f"Error leyendo archivo TOML: {e}"
            raise ValueError(msg) from e

        # Convertir estructura TOML anidada a estructura plana para Pydantic
        config_dict: dict[str, Any] = {}

        # Server
        if "server" in data:
            config_dict["server"] = data["server"]

        # Game
        if "game" in data:
            game_data = data["game"]
            config_dict["game"] = {
                "max_players_per_map": game_data.get("max_players_per_map", 100),
                "respawn_check_interval": game_data.get("respawn_check_interval", 5.0),
                "npc_respawn_base_time": game_data.get("npc_respawn_base_time", 30.0),
                "npc_respawn_random_variance": game_data.get("npc_respawn_random_variance", 15.0),
                "combat": game_data.get("combat", {}),
                "work": game_data.get("work", {}),
                "stamina": game_data.get("stamina", {}),
                "hunger_thirst": game_data.get("hunger_thirst", {}),
                "gold_decay": game_data.get("gold_decay", {}),
                "inventory": game_data.get("inventory", {}),
                "bank": game_data.get("bank", {}),
                "character": game_data.get("character", {}),
            }

        # Logging
        if "logging" in data:
            config_dict["logging"] = data["logging"]

        # Redis
        if "redis" in data:
            config_dict["redis"] = data["redis"]

        try:
            # Crear instancia desde TOML
            # Nota: Cuando se carga desde TOML, los valores del TOML tienen prioridad
            # sobre las variables de entorno (comportamiento estándar de Pydantic Settings).
            #
            # Para que las variables de entorno tengan prioridad, usa GameConfig() directamente
            # sin from_toml, o establece las variables de entorno ANTES de llamar from_toml.
            return cls(**config_dict)
        except Exception as e:
            msg = f"Error validando configuración: {e}"
            raise ValueError(msg) from e

    def to_dict(self) -> dict[str, Any]:
        """Convierte la configuración a diccionario.

        Returns:
            Diccionario con toda la configuración.
        """
        return self.model_dump()

    def get(self, key: str, default: ConfigValue | None = None) -> ConfigValue:
        """Obtiene un valor de configuración usando notación de puntos.

        Compatible con ConfigManager.get() para migración gradual.

        Args:
            key: Clave de configuración (ej: "server.port", "game.combat.base_critical_chance").
            default: Valor por defecto si no se encuentra.

        Returns:
            Valor de configuración o default.
        """
        keys = key.split(".")
        value: BaseModel | dict[str, Any] | ConfigValue = self

        try:
            for k in keys:
                if isinstance(value, BaseModel):
                    value = getattr(value, k)
                elif isinstance(value, dict):
                    value = value[k]
                else:
                    return default
        except (AttributeError, KeyError, TypeError):
            return default

        # Convertir BaseModel a dict si es necesario para compatibilidad
        if isinstance(value, BaseModel):
            return value.model_dump()
        return value

    def set(self, key: str, value: ConfigValue) -> None:
        """Establece un valor de configuración usando notación de puntos.

        Args:
            key: Clave de configuración (ej: "server.port").
            value: Nuevo valor (debe ser válido según el modelo).

        Raises:
            TypeError: Si la ruta es inválida o el objeto no es BaseModel.
        """
        keys = key.split(".")
        obj: BaseModel | dict[str, Any] = self

        # Navegar hasta el penúltimo nivel
        for k in keys[:-1]:
            if isinstance(obj, BaseModel):
                obj = getattr(obj, k)
            elif isinstance(obj, dict):
                obj = obj[k]
            else:
                msg = f"No se puede establecer {key}: ruta inválida"
                raise TypeError(msg)

        # Establecer el valor
        if isinstance(obj, BaseModel):
            setattr(obj, keys[-1], value)
        else:
            msg = f"No se puede establecer {key}: objeto no es BaseModel"
            raise TypeError(msg)

    def reload(self, toml_path: Path | str | None = None) -> None:
        """Recarga la configuración desde archivo TOML.

        Args:
            toml_path: Ruta al archivo TOML. Si es None, usa el path por defecto.
        """
        if toml_path is None:
            toml_path = Path(__file__).parent.parent.parent / "config" / "server.toml"

        new_config = self.from_toml(toml_path)
        # Actualizar valores
        self.server = new_config.server
        self.game = new_config.game
        self.logging = new_config.logging
        self.redis = new_config.redis

        logger.info("Configuración recargada desde %s", toml_path)


# Singleton para la instancia global de configuración
class _ConfigSingleton:
    """Singleton para la instancia global de configuración."""

    _instance: GameConfig | None = None

    @classmethod
    def get(cls, toml_path: Path | str | None = None) -> GameConfig:
        """Obtiene la instancia global de configuración.

        Args:
            toml_path: Ruta al archivo TOML. Solo se usa en la primera llamada.

        Returns:
            Instancia global de GameConfig.
        """
        if cls._instance is None:
            if toml_path is None:
                toml_path = Path(__file__).parent.parent.parent / "config" / "server.toml"

            try:
                cls._instance = GameConfig.from_toml(toml_path)
                logger.info("Configuración cargada desde %s", toml_path)
            except FileNotFoundError:
                logger.warning("Archivo de configuración no encontrado, usando defaults")
                cls._instance = GameConfig()
            except Exception:
                logger.exception("Error cargando configuración, usando defaults")
                cls._instance = GameConfig()

        return cls._instance


def get_game_config(toml_path: Path | str | None = None) -> GameConfig:
    """Obtiene la instancia global de configuración.

    Args:
        toml_path: Ruta al archivo TOML. Solo se usa en la primera llamada.

    Returns:
        Instancia global de GameConfig.
    """
    return _ConfigSingleton.get(toml_path)


# Instancia global para compatibilidad
game_config = get_game_config()
