"""Lectura compartida de archivos NDJSON de mapas."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def iter_ndjson_entries(
    path: Path,
    *,
    log: logging.Logger | None = None,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """Yield ``(line_number, parsed_dict)`` por línea no vacía del archivo."""
    active_log = log or logger

    with path.open(encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                active_log.debug(
                    "Entrada inválida en %s línea %d: %s",
                    path.name,
                    line_number,
                    line,
                )
                continue

            if not isinstance(entry, dict):
                continue

            yield line_number, entry
