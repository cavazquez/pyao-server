"""Paquete de configuración del servidor."""

from .config_manager import config_manager

# Compatibilidad con el viejo sistema
config = config_manager

__all__ = ["config", "config_manager"]
