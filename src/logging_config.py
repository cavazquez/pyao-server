"""Configuración de logging por features/módulos."""

import logging
import os
from typing import ClassVar, Literal

# Niveles de logging disponibles
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

# Configuración de features para logging
# Cada feature puede tener su propio nivel de logging
FEATURE_LOG_LEVELS: dict[str, LogLevel] = {
    # Core (siempre en INFO para ver mensajes de inicio/fin)
    "core": "INFO",
    "core.server_initializer": "INFO",  # Mensajes de servidor listo
    "server": "INFO",
    # Network
    "network": "WARNING",
    "packets": "WARNING",
    # Tasks
    "tasks": "WARNING",
    "tasks.party": "INFO",  # Party tasks en INFO para debugging
    "tasks.player": "INFO",
    "tasks.combat": "WARNING",
    # Services
    "services": "WARNING",
    "services.party": "INFO",  # Party service en INFO para debugging
    "services.map": "INFO",  # Map service en INFO para ver carga de recursos
    "services.npc": "WARNING",
    # Messaging
    "messaging": "INFO",  # INFO para ver logs de envío de packets importantes
    "messaging.console": "WARNING",
    # Effects
    "effects": "WARNING",
    # Repositories
    "repositories": "WARNING",
    # Game
    "game": "WARNING",
}

# Nivel por defecto para módulos no especificados
DEFAULT_LOG_LEVEL: LogLevel = "WARNING"


class ColorFormatter(logging.Formatter):
    """Formatter con colores ANSI opcionales."""

    COLORS: ClassVar[dict[str, str]] = {
        "DEBUG": "\033[36m",  # cyan
        "INFO": "\033[32m",  # green
        "WARNING": "\033[33m",  # yellow
        "ERROR": "\033[31m",  # red
        "CRITICAL": "\033[41m",  # red background
    }
    RESET: ClassVar[str] = "\033[0m"

    def __init__(self, fmt: str, datefmt: str, use_color: bool) -> None:
        """Inicializa el formatter con o sin colores ANSI."""
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        """Devuelve el mensaje formateado aplicando color al nivel si corresponde.

        Returns:
            str: Mensaje listo para imprimir en el handler.
        """
        original_level = record.levelname
        if self.use_color and original_level in self.COLORS:
            record.levelname = f"{self.COLORS[original_level]}{original_level}{self.RESET}"
        try:
            return super().format(record)
        finally:
            record.levelname = original_level


def configure_logging() -> None:
    """Configura el logging según las features definidas."""
    use_color = os.getenv("NO_COLOR") is None
    force_color = os.getenv("LOG_COLOR", "").lower() in {"1", "true", "yes"}

    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)

    # Habilitar color cuando hay TTY o si se fuerza vía LOG_COLOR=1/true/yes
    handler_use_color = use_color and (
        force_color or getattr(handler.stream, "isatty", lambda: False)()
    )

    handler.setFormatter(
        ColorFormatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            use_color=handler_use_color,
        )
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)

    # Aplicar niveles específicos por feature
    for feature, level in FEATURE_LOG_LEVELS.items():
        logger_name = f"src.{feature.replace('.', '.')}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, level))

    # Silenciar librerías externas ruidosas
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("redis").setLevel(logging.WARNING)


def set_feature_log_level(feature: str, level: LogLevel) -> None:
    """Cambia el nivel de logging de una feature en runtime.

    Args:
        feature: Nombre de la feature (ej: "services.party", "tasks.combat")
        level: Nivel de logging ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")

    Example:
        >>> set_feature_log_level("services.party", "DEBUG")
        >>> set_feature_log_level("tasks", "INFO")
    """
    FEATURE_LOG_LEVELS[feature] = level
    logger_name = f"src.{feature.replace('.', '.')}"
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level))
    config_logger = logging.getLogger(__name__)
    config_logger.info("Changed log level for %s to %s", feature, level)


def enable_debug_for_feature(feature: str) -> None:
    """Activa DEBUG para una feature específica.

    Args:
        feature: Nombre de la feature (ej: "services.party")

    Example:
        >>> enable_debug_for_feature("services.party")
    """
    set_feature_log_level(feature, "DEBUG")


def disable_debug_for_feature(feature: str) -> None:
    """Desactiva DEBUG para una feature (vuelve a WARNING).

    Args:
        feature: Nombre de la feature

    Example:
        >>> disable_debug_for_feature("services.party")
    """
    set_feature_log_level(feature, "WARNING")


# Presets comunes
def enable_party_debug() -> None:
    """Activa logging detallado para todo el sistema de party."""
    logger = logging.getLogger(__name__)
    enable_debug_for_feature("services.party")
    enable_debug_for_feature("tasks.party")
    logger.info("✓ Party debug mode enabled")


def enable_combat_debug() -> None:
    """Activa logging detallado para sistema de combate."""
    logger = logging.getLogger(__name__)
    enable_debug_for_feature("tasks.combat")
    enable_debug_for_feature("services.npc")
    logger.info("✓ Combat debug mode enabled")


def enable_network_debug() -> None:
    """Activa logging detallado para red y packets."""
    logger = logging.getLogger(__name__)
    enable_debug_for_feature("network")
    enable_debug_for_feature("packets")
    enable_debug_for_feature("messaging")
    logger.info("✓ Network debug mode enabled")


def quiet_mode() -> None:
    """Modo silencioso - solo errores.

    Nota: Los mensajes de core (inicio/fin del servidor) siempre se muestran.
    """
    logger = logging.getLogger(__name__)
    for feature in FEATURE_LOG_LEVELS:
        # Mantener core en INFO para ver mensajes de inicio/fin
        if feature.startswith("core"):
            continue
        set_feature_log_level(feature, "ERROR")
    logger.info("✓ Quiet mode enabled (errors only, core messages visible)")


def verbose_mode() -> None:
    """Modo verbose - todo en DEBUG.

    Usado cuando se inicia el servidor con la opción --debug para mostrar
    logs detallados de todos los módulos/features.
    """
    logger = logging.getLogger(__name__)
    for feature in FEATURE_LOG_LEVELS:
        set_feature_log_level(feature, "DEBUG")
    logger.info("✓ Verbose mode enabled (DEBUG for all features)")
