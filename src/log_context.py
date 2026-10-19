"""Correlación acotada al task asíncrono, sin guardar payloads o credenciales."""

import json
import logging
import re
import traceback
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

connection_id: ContextVar[str] = ContextVar("connection_id", default="")
operation_id: ContextVar[str] = ContextVar("operation_id", default="")
_SECRET = re.compile(
    r"""(?i)((?:password|passwd|token|account_hash|authorization|auth_payload)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|(?:Bearer\s+)?[^,;\s}]+)"""
)


@contextmanager
def operation(identity: str) -> Iterator[None]:
    """Propaga identidad sólo durante una petición y sus awaits."""
    token = operation_id.set(identity[:64])
    try:
        yield
    finally:
        operation_id.reset(token)


class SafeLogFilter(logging.Filter):
    """Aplica el mismo filtro al formato humano y al JSON."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Oculta campos sensibles antes de formatear o serializar.

        Returns:
            True para conservar el registro ya saneado.
        """
        record.msg = _SECRET.sub(r"\1[REDACTED]", record.getMessage())
        record.args = ()
        return True


class JSONFormatter(logging.Formatter):
    """Esquema estable con contexto por conexión y sin objetos serializados arbitrarios."""

    def format(self, record: logging.LogRecord) -> str:
        """Devuelve un registro JSON; las excepciones omiten argumentos sensibles.

        Returns:
            Una línea JSON sin objetos arbitrarios ni argumentos de excepción.
        """
        fields = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "component": record.name,
            "connection_id": connection_id.get(),
            "operation_id": operation_id.get(),
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            fields["exception"] = record.exc_info[0].__name__
            fields["stack"] = "".join(traceback.format_tb(record.exc_info[2], limit=8))
        return json.dumps(fields, ensure_ascii=False)
