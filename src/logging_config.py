"""Configuración de logging por features/módulos."""

import logging
from typing import Literal

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
    "tasks.player": "WARNING",
    "tasks.combat": "WARNING",
    # Services
    "services": "WARNING",
    "services.party": "INFO",  # Party service en INFO para debugging
    "services.map": "WARNING",
    "services.npc": "WARNING",
    # Messaging
    "messaging": "WARNING",
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


def configure_logging() -> None:
    """Configura el logging según las features definidas."""
    # Configuración base
    logging.basicConfig(
        level=logging.DEBUG,  # Nivel más bajo para capturar todo
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

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
    """Modo verbose - todo en INFO."""
    logger = logging.getLogger(__name__)
    for feature in FEATURE_LOG_LEVELS:
        set_feature_log_level(feature, "INFO")
    logger.info("✓ Verbose mode enabled")
