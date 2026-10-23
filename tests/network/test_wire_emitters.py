"""Golden bytes de emisores que no pasan por los constructores msg_* básicos."""

import json
import operator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.messaging.message_sender import MessageSender
from src.network.capabilities import SUPPORTED_CAPABILITIES, ConnectionCapabilities
from src.network.packet_framer import CONTRACT
from src.network.state_channel import send_state
from src.services.player.lifetime_stats import mini_stats_packet
from src.services.trade_service import TradeService, TradeSession, TradeState
from src.services.visual_events import VisualEvents
from src.tasks.task_capabilities import TaskCapabilities
from src.tasks.task_skill_action import TaskSkillAction

FIXTURES = json.loads(
    (Path(__file__).parents[2] / "src/network/protocol/fixtures.json").read_text()
)
EMITTERS = [fixture for fixture in FIXTURES if "emitter" in fixture]


def test_every_supported_server_message_has_a_real_writer():
    """No basta construir bytes sintéticos desde el contrato."""
    covered = {
        int(fixture["hex"][:2], 16)
        for fixture in FIXTURES
        if "python" in fixture or "emitter" in fixture
    }
    expected = {
        int(key)
        for key, value in CONTRACT["directions"]["server"].items()
        if value["status"] == "supported"
    }
    assert covered == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("fixture", EMITTERS, ids=operator.itemgetter("name"))
async def test_real_emitter_matches_shared_golden(fixture):
    """Ejecuta el emisor de producción y compara bytes conocidos por Godot."""
    connection = SimpleNamespace(
        send=AsyncMock(),
        address=("127.0.0.1", 1),
        is_authenticated=True,
        capabilities=SimpleNamespace(enabled=SUPPORTED_CAPABILITIES),
        session_redis=None,
        session_user_id=None,
        state_epoch="a" * 32,
        state_sequence=0,
    )
    sender = MessageSender(connection)
    maps = SimpleNamespace(
        get_players_in_map=lambda _map: [1],
        get_player_message_sender=lambda user: sender if user == 1 else None,
    )
    emitter, values = fixture["emitter"], fixture["values"]
    kind = emitter["kind"]
    if kind == "sender":
        await getattr(sender, emitter["method"])(*emitter["args"])
    elif kind == "mini_stats":
        player = SimpleNamespace(
            redis=SimpleNamespace(
                hgetall=AsyncMock(
                    return_value={
                        key: str(values[key])
                        for key in [
                            "citizen_kills",
                            "criminal_kills",
                            "player_kills",
                            "npc_kills",
                            "deaths",
                        ]
                    }
                )
            )
        )
        account = SimpleNamespace(
            get_account_by_user_id=AsyncMock(return_value={"char_job": str(values["class"])})
        )
        with patch("src.services.player.lifetime_stats.remaining_days", return_value=2):
            await connection.send(await mini_stats_packet(player, account, 1))
    elif kind == "capabilities":
        connection.capabilities = ConnectionCapabilities()
        connection.capabilities.after_login()
        await TaskCapabilities(bytes([250, 1, 0, 0, 0, 0]), sender).execute()
    elif kind == "skill_reply":
        result = json.loads(values["result"])
        identity = result.pop("id")
        await TaskSkillAction(b"", sender)._reply(identity, result)
    elif kind == "world":
        state = json.loads(values["payload"])
        await send_state(
            sender, state["kind"], state["data"], identity=state["id"], revision=state["revision"]
        )
    elif kind == "damage":
        await VisualEvents(maps).damage("fixture-visual", 2, 7, 50, 51, 20, 4)
    elif kind == "projectile":
        await VisualEvents(maps).projectile("fixture-visual", 2, 7, 8, 50, 51, 52, 51, 1, 7, 2)
    elif kind == "trade":
        from src.services.trade_service import TradeOfferItem  # ruff: ignore[import-outside-top-level]

        service = TradeService(SimpleNamespace(), SimpleNamespace(), maps, monitor=False)
        session = TradeSession(
            1,
            "Alice",
            2,
            "Bob",
            TradeState.ACTIVE,
            0,
            0,
            session_id="a" * 32,
            revision=1,
            senders={1: sender},
        )
        session.initiator_offer.items[30] = TradeOfferItem(30, 101, 2)
        session.target_offer.gold = 10
        await service._publish(session)
    else:
        pytest.fail("Emisor sin prueba: " + kind)
    connection.send.assert_awaited_once_with(bytes.fromhex(fixture["hex"]))
