"""Ubicaciones de recursos inmutables y estado editable, independientes del cwd."""

import hashlib
import os
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

SOURCE_ROOT = Path(__file__).resolve().parents[1]
BUNDLED_ROOT = Path(__file__).resolve().parent / "runtime_data"


def resource_root() -> Path:
    """Devuelve recursos del wheel o del checkout de desarrollo.

    Returns:
        Directorio de recursos inmutables.
    """
    return BUNDLED_ROOT if BUNDLED_ROOT.is_dir() else SOURCE_ROOT


def data_dir() -> Path:
    """Ubica el dataset propio, con override explícito y compatibilidad Snap.

    Returns:
        Directorio de catálogos TOML.
    """
    if value := os.environ.get("PYAO_DATA_DIR"):
        return Path(value).expanduser().resolve()
    if (snap := os.environ.get("SNAP_USER_COMMON")) and (Path(snap) / "data").is_dir():
        return Path(snap) / "data"
    return resource_root() / "data"


def state_dir() -> Path:
    """Ubica cachés, certificados y datos editables fuera del paquete instalado.

    Returns:
        Directorio editable del operador.
    """
    if value := os.environ.get("PYAO_STATE_DIR") or os.environ.get("SNAP_USER_COMMON"):
        return Path(value).expanduser().resolve()
    if not BUNDLED_ROOT.is_dir():
        return SOURCE_ROOT
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData/Local"))) / "PyAO"
    return Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "pyao-server"


def config_file() -> Path:
    """Usa configuración explícita, editable del usuario o defaults del paquete.

    Returns:
        Archivo TOML efectivo.
    """
    if value := os.environ.get("PYAO_CONFIG_FILE"):
        return Path(value).expanduser().resolve()
    editable = state_dir() / "config/server.toml"
    return editable if editable.is_file() else resource_root() / "config/server.toml"


def maps_dir() -> Path:
    """Extrae el archive versionado a una caché por hash sin escribir en el wheel.

    Returns:
        Dataset de mapas explícito, del checkout o extraído del paquete.
    """
    if value := os.environ.get("PYAO_MAPS_DIR"):
        return Path(value).expanduser().resolve()
    if not BUNDLED_ROOT.is_dir():
        return SOURCE_ROOT / "map_data"
    archive = resource_root() / "archives/map_data.xz"
    with archive.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    destination = state_dir() / "maps" / digest
    if destination.is_dir():
        return destination
    # La extracción existente valida rutas y límites antes de escribir cada entrada.
    from tools.compression.decompress_map_data import decompress_map_data  # noqa: PLC0415

    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="extract-", dir=destination.parent) as temporary:
        staging = Path(temporary) / "maps"
        decompress_map_data(archive, staging, overwrite=False)
        # Otra instancia puede haber extraído exactamente el mismo archive.
        with suppress(FileExistsError):
            staging.rename(destination)
    return destination
