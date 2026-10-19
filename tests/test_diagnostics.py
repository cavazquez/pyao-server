"""El diagnóstico nunca inicializa el mundo ni modifica el Redis inspeccionado."""

import argparse
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from src.diagnostics import diagnose


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [None, "redis", "dataset", "configuration", "tls"])
async def test_read_only_diagnostic_reports_missing_dependencies(monkeypatch, tmp_path, failure):
    """La salida es accionable, no filtra secretos y sólo permite PING/cierre."""
    from src.config import game_config  # ruff: ignore[import-outside-top-level]
    from src.validation.dataset import DatasetValidator  # ruff: ignore[import-outside-top-level]

    secret = "SYNTHETIC_DIAGNOSTIC_PRIVATE"
    config = SimpleNamespace(
        redis=SimpleNamespace(host="127.0.0.1", port=17666, db=0, read_password=lambda: secret)
    )
    monkeypatch.setattr(
        game_config,
        "get_game_config",
        Mock(side_effect=ValueError(secret)) if failure == "configuration" else lambda: config,
    )
    validate = Mock(return_value=SimpleNamespace(errors=[]))
    if failure == "dataset":
        validate.side_effect = FileNotFoundError(secret)
    monkeypatch.setattr(DatasetValidator, "validate", validate)
    redis = Mock(spec=["ping", "aclose"])
    redis.ping = AsyncMock(return_value=True)
    redis.aclose = AsyncMock()
    if failure == "redis":
        redis.ping.side_effect = RedisConnectionError(secret)
    constructor = Mock(return_value=redis)
    monkeypatch.setattr("src.diagnostics.Redis", constructor)
    result = await diagnose(
        argparse.Namespace(
            ssl=failure == "tls", ssl_cert=str(tmp_path / "missing.crt"), ssl_key=None
        )
    )
    assert result["ok"] is (failure is None)
    assert secret not in json.dumps(result)
    if failure == "configuration":
        constructor.assert_not_called()
    else:
        redis.ping.assert_awaited_once_with()
        redis.aclose.assert_awaited_once_with()
    if failure:
        check = next(row for row in result["checks"] if row["name"] == failure)
        assert check["ok"] is False
        assert "Revisar" in check["message"]
