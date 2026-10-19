"""Correlación por petición y ausencia de canarios en ambos formatos."""

import json
import logging
from io import StringIO

import pytest

from src.log_context import JSONFormatter, SafeLogFilter, connection_id, operation
from src.logging_config import FEATURE_LOG_LEVELS, configure_logging, verbose_mode


def test_sensitive_fields_and_exception_arguments_are_not_serialized():
    """El formateo excluye campos sensibles incluso con espacios o Bearer."""
    canary = "SYNTHETIC PRIVATE CANARY"
    record = logging.LogRecord(
        "component",
        logging.ERROR,
        "test",
        1,
        'password="%s", authorization=Bearer abc123, token=xyz',
        (canary,),
        None,
    )
    assert SafeLogFilter().filter(record)
    result = JSONFormatter().format(record)
    assert canary not in result
    assert "abc123" not in result
    assert "xyz" not in result
    assert json.loads(result)["component"] == "component"


def test_nested_operation_context_is_restored():
    """La identidad de operación no permanece en la petición siguiente."""
    token = connection_id.set("connection-a")
    try:
        with operation("op-a"):
            record = logging.LogRecord("component", logging.INFO, "test", 1, "confirmed", (), None)
            assert json.loads(JSONFormatter().format(record))["operation_id"] == "op-a"
        assert not json.loads(JSONFormatter().format(record))["operation_id"]
    finally:
        connection_id.reset(token)


@pytest.mark.parametrize("format_name", ["json", "text"])
def test_verbose_output_is_reachable_and_redacted_in_both_formats(monkeypatch, format_name):
    """--debug atraviesa el handler y nunca publica el secreto de un error."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    levels = {f"src.{name}": logging.getLogger(f"src.{name}").level for name in FEATURE_LOG_LEVELS}
    stream = StringIO()
    monkeypatch.setenv("PYAO_LOG_FORMAT", format_name)
    monkeypatch.setattr("sys.stderr", stream)
    secret = "SYNTHETIC VERBOSE PRIVATE"
    try:
        configure_logging()
        verbose_mode()
        component = logging.getLogger("src.command_handlers.walk_handler")
        component.debug('password="%s"', secret)
        component.error("Operación fallida", exc_info=(ValueError, ValueError(secret), None))
        output = stream.getvalue()
        assert secret not in output
        assert "[REDACTED]" in output
        assert "DEBUG" in output
        assert "ValueError" in output
        if format_name == "json":
            assert all(isinstance(json.loads(line), dict) for line in output.splitlines())
    finally:
        root.handlers = handlers
        root.setLevel(level)
        for name, previous in levels.items():
            logging.getLogger(name).setLevel(previous)
