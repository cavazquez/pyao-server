"""Correlación por petición y ausencia de canarios en ambos formatos."""

import json
import logging

from src.log_context import JSONFormatter, SafeLogFilter, connection_id, operation


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
