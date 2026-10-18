"""Permisos, sesión mutable y presupuesto de METRICS."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.talk_metrics_handler import TalkMetricsHandler


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["ordinary", "revoked", "session", "disconnected", "admin"])
async def test_details_require_current_admin_before_collection_and_emission(change):
    """No alcanza ocultar el comando o autorizarlo una sola vez."""
    session = {"user_id": 1}
    sender = SimpleNamespace(
        connection=SimpleNamespace(is_authenticated=True),
        send_console_msg=AsyncMock(),
        send_multiline_console_msg=AsyncMock(),
    )
    account = SimpleNamespace(
        is_gm_by_user_id=AsyncMock(
            side_effect=[True, False] if change == "revoked" else None,
            return_value=change != "ordinary",
        )
    )
    tick = MagicMock(effects=[])

    def collect():
        if change == "session":
            session["user_id"] = 2
        if change == "disconnected":
            sender.connection.is_authenticated = False
        return {"total_ticks": 10, "avg_tick_time_ms": 1.0, "max_tick_time_ms": 2.0, "effects": {}}

    tick.get_metrics.side_effect = collect
    await TalkMetricsHandler(tick, sender, account, session).handle_metrics_command(1)
    assert sender.send_multiline_console_msg.await_count == (1 if change == "admin" else 0)
    assert tick.get_metrics.call_count == (0 if change == "ordinary" else 1)


@pytest.mark.asyncio
async def test_slow_authorization_does_not_collect_or_outlive_budget(monkeypatch):
    """Un backend detenido no mantiene una consulta operativa indefinidamente."""

    async def stalled(_user):
        await asyncio.Future()

    monkeypatch.setattr("src.command_handlers.talk_metrics_handler.METRICS_BUDGET_SECONDS", 0.001)
    sender = SimpleNamespace(
        connection=SimpleNamespace(is_authenticated=True), send_console_msg=AsyncMock()
    )
    tick = MagicMock()
    account = SimpleNamespace(is_gm_by_user_id=stalled)
    await asyncio.wait_for(
        TalkMetricsHandler(tick, sender, account, {"user_id": 1}).handle_metrics_command(1), 1
    )
    tick.get_metrics.assert_not_called()
