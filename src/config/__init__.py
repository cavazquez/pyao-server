"""Paquete de configuración del servidor."""

from .config_manager import config_manager
from .config_manager import config_manager as config  # Re-export para compatibilidad

__all__ = ["config", "config_manager"]
