"""Módulo para obtener la versión del paquete."""

try:
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("pyao-server")
except PackageNotFoundError:
    __version__ = "unknown"
