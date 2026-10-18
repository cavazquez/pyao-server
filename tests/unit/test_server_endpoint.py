"""Precedencia del endpoint efectivo hasta asyncio.start_server."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from src.config.game_config import GameConfig
from src.server import ArgentumServer


@pytest.mark.asyncio
async def test_cli_endpoint_survives_initialization():
    """Redis no puede sustituir un bind explícito del operador."""
    listener = MagicMock()
    listener.sockets = []
    listener.serve_forever = AsyncMock(side_effect=asyncio.CancelledError)
    deps = MagicMock()
    server = ArgentumServer(host="127.0.0.1", port=7777)
    with (
        patch(
            "src.server.ServerInitializer.initialize_all",
            AsyncMock(return_value=(deps, "0.0.0.0", 7666)),
        ),
        patch("src.server.asyncio.start_server", AsyncMock(return_value=listener)) as start,
        pytest.raises(asyncio.CancelledError),
    ):
        await server.start()
    assert start.call_args.args[1:] == ("127.0.0.1", 7777)


def test_environment_overrides_file_and_file_overrides_defaults(tmp_path, monkeypatch):
    """Cada campo conserva su origen sin perder otros campos del TOML."""
    path = tmp_path / "server.toml"
    path.write_text('[server]\nhost="127.0.0.2"\nport=8888\nmax_connections=23\n')
    config = GameConfig.from_toml(path)
    assert config.server.host == "127.0.0.2"
    assert config.server.port == 8888
    monkeypatch.setenv("PYAO_SERVER__PORT", "9999")
    config = GameConfig.from_toml(path)
    assert config.server.port == 9999
    assert config.server.host == "127.0.0.2"
    assert config.server.max_connections == 23
    assert GameConfig(_env_file=None).server.host == "0.0.0.0"


@pytest.mark.parametrize("port", [0, -1, 65536])
def test_explicit_invalid_port_is_not_replaced_by_a_default(port):
    """Un valor inválido falla antes de inicializar Redis o aceptar jugadores."""
    with pytest.raises(ValidationError):
        ArgentumServer(host="127.0.0.1", port=port)
