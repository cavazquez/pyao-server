# ruff: noqa: D103, D107
"""Tests para TradeService."""

import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.models.item_constants import MAX_PLAYER_GOLD
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.trade_service import TradeService


class DummySender:
    """Mock simple de MessageSender."""

    def __init__(self) -> None:
        self.init_payloads: list[str] = []
        self.end_calls = 0
        self.send_change_inventory_slot = AsyncMock()
        self.send_update_gold = AsyncMock()
        self.console_messages: list[tuple[str, int]] = []

    async def send_user_commerce_init(self, partner_username: str) -> None:
        self.init_payloads.append(partner_username)

    async def send_user_commerce_end(self) -> None:
        self.end_calls += 1

    async def send_console_msg(self, message: str, font_color: int = 7) -> None:
        self.console_messages.append((message, font_color))


class DummyMapManager:
    """Stub de MapManager para los tests."""

    def __init__(self) -> None:
        self._users: dict[int, tuple[DummySender, str]] = {}

    def add_player(self, user_id: int, username: str) -> DummySender:
        sender = DummySender()
        self._users[user_id] = (sender, username)
        return sender

    def find_player_by_username(self, username: str) -> int | None:
        username_lower = username.lower().strip()
        for user_id, (_, name) in self._users.items():
            if name.lower().strip() == username_lower:
                return user_id
        return None

    def get_player_username(self, user_id: int) -> str | None:
        entry = self._users.get(user_id)
        return entry[1] if entry else None

    def get_player_message_sender(self, user_id: int) -> DummySender | None:
        entry = self._users.get(user_id)
        return entry[0] if entry else None


@pytest_asyncio.fixture
async def setup_trade(redis_client):
    """Usa recursos concretos y sustituye I/O de mensajería/fsync en tests rápidos.

    Yields:
        Servicio, mapa y repositorios con Redis fake compartido.
    """
    manager = DummyMapManager()
    manager.add_player(1, "Alice")
    manager.add_player(2, "Bob")
    player = PlayerRepository(redis_client)
    inventory = InventoryRepository(redis_client)
    await player.update_gold(1, 100)
    await player.update_gold(2, 200)
    await inventory.set_slot(1, 1, 101, 5)
    await inventory.set_slot(2, 2, 202, 3)
    await player.set_position(1, 50, 50, 1)
    await player.set_position(2, 51, 50, 1)
    for user in [1, 2]:
        await player.redis.hset(f"player:{user}:user_stats", mapping={"min_hp": "100"})
    service = TradeService(player, inventory, manager, monitor=False)
    with patch("src.services.trade_settlement.require_durable", new=AsyncMock()):
        yield service, manager, player, inventory


@pytest.mark.asyncio
async def test_request_validation_and_cancel(setup_trade):
    service, manager, _player, _inventory = setup_trade
    assert not (await service.request_trade(1, "Missing"))[0]
    assert not (await service.request_trade(1, "Alice"))[0]
    assert (await service.request_trade(1, "bob"))[0]
    assert service.get_session(1) is service.get_session(2)
    assert manager.get_player_message_sender(1).init_payloads == ["Bob"]
    assert not (await service.request_trade(2, "Alice"))[0]
    assert (await service.cancel_trade(1))[0]
    assert not (await service.cancel_trade(2))[0]
    assert manager.get_player_message_sender(1).end_calls == 1
    assert manager.get_player_message_sender(2).end_calls == 1
    assert not (await service.confirm_trade(1))[0]


@pytest.mark.asyncio
async def test_offer_preconditions(setup_trade):
    service, _manager, _player, _inventory = setup_trade
    assert (await service.request_trade(1, "Bob"))[0]
    assert not (await service.update_offer(1, 1, 6))[0]
    assert not (await service.update_offer(1, 0, 101))[0]
    assert not (await service.update_offer(1, 31, 1))[0]
    assert not (await service.update_offer(1, 1, -1))[0]


@pytest.mark.asyncio
async def test_concurrent_confirm_moves_both_resources_once(setup_trade):
    service, manager, player, inventory = setup_trade
    await service.request_trade(1, "Bob")
    await service.update_offer(1, 1, 2)
    await service.update_offer(2, 2, 1)
    await service.update_offer(1, 0, 20)
    await service.update_offer(2, 0, 60)
    session = service.get_session(1)
    await asyncio.gather(
        service.confirm_trade(1), service.confirm_trade(2), service.confirm_trade(2)
    )
    assert await inventory.get_slot(1, 1) == (101, 3)
    assert await inventory.get_slot(1, 2) == (202, 1)
    assert await inventory.get_slot(2, 1) == (101, 2)
    assert await inventory.get_slot(2, 2) == (202, 2)
    assert await player.get_gold(1) == 140
    assert await player.get_gold(2) == 160
    assert not service.is_user_in_trade(1)
    assert not service.is_user_in_trade(2)
    assert session.settlement_id
    for user_id in [1, 2]:
        sender = manager.get_player_message_sender(user_id)
        assert sender.end_calls == 1
        assert sender.send_change_inventory_slot.await_count == 30


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["source_changed", "full", "overflow", "equipped"])
async def test_rejected_settlement_preserves_every_resource(setup_trade, reason):
    service, _manager, player, inventory = setup_trade
    await service.request_trade(1, "Bob")
    await service.update_offer(1, 1, 2)
    await service.update_offer(1, 0, 20)
    if reason == "source_changed":
        await inventory.set_slot(1, 1, 101, 1)
    elif reason == "full":
        for slot in range(1, 31):
            await inventory.set_slot(2, slot, 202, 20)
    elif reason == "overflow":
        await player.update_gold(2, MAX_PLAYER_GOLD)
    else:
        await player.redis.hset("player:1:equipment", mapping={"weapon": "1"})
    before = [await inventory.get_inventory(i) for i in [1, 2]]
    balances = [await player.get_gold(i) for i in [1, 2]]
    await service.confirm_trade(1)
    assert not (await service.confirm_trade(2))[0]
    assert [await inventory.get_inventory(i) for i in [1, 2]] == before
    assert [await player.get_gold(i) for i in [1, 2]] == balances


@pytest.mark.asyncio
async def test_unknown_durability_result_is_retried_without_reapplying(setup_trade):
    service, _manager, player, _inventory = setup_trade
    await service.request_trade(1, "Bob")
    await service.update_offer(1, 0, 20)
    await service.confirm_trade(1)
    failure = RuntimeError("fsync acknowledgment lost")
    with (
        patch(
            "src.services.trade_settlement.require_durable",
            new=AsyncMock(side_effect=[None, failure]),
        ),
        pytest.raises(RuntimeError, match="fsync"),
    ):
        await service.confirm_trade(2)
    assert await player.get_gold(1) == 80
    assert await player.get_gold(2) == 220
    assert not (await service.update_offer(1, 0, 1))[0]
    assert (await service.cancel_trade(1))[0]  # El commit ya ganó; informa éxito, sin reembolsar.
    assert not (await service.confirm_trade(1))[0]
    assert await player.get_gold(1) == 80
    assert await player.get_gold(2) == 220


@pytest.mark.asyncio
async def test_offer_read_racing_with_commit_cannot_change_frozen_offer(setup_trade):
    """Una lectura de slot que empezó antes no edita una oferta ya en confirmación."""
    service, _manager, player, inventory = setup_trade
    await service.request_trade(1, "Bob")
    await service.update_offer(1, 0, 20)
    entered_read, resume_read = asyncio.Event(), asyncio.Event()
    entered_commit, resume_commit = asyncio.Event(), asyncio.Event()
    original = inventory.get_slot

    async def slow_read(user_id: int, slot: int):
        value = await original(user_id, slot)
        entered_read.set()
        await resume_read.wait()
        return value

    async def slow_durability(_redis: object) -> None:
        entered_commit.set()
        await resume_commit.wait()

    with (
        patch.object(inventory, "get_slot", slow_read),
        patch("src.services.trade_settlement.require_durable", slow_durability),
    ):
        edit = asyncio.create_task(service.update_offer(1, 1, 2))
        await asyncio.wait_for(entered_read.wait(), 2)
        await service.confirm_trade(1)
        commit = asyncio.create_task(service.confirm_trade(2))
        await asyncio.wait_for(entered_commit.wait(), 2)
        resume_read.set()
        assert not (await edit)[0]
        resume_commit.set()
        assert (await commit)[0]
    assert await inventory.get_slot(1, 1) == (101, 5)
    assert await player.get_gold(1) == 80


def modern(service, manager):
    for user in (1, 2):
        sender = manager.get_player_message_sender(user)
        sender.connection = SimpleNamespace(
            capabilities=SimpleNamespace(enabled=128), send=AsyncMock()
        )
    service.clock = lambda: 100.0


@pytest.mark.asyncio
async def test_revision_snapshots_stale_confirmation_and_acceptance(setup_trade):
    service, manager, _player, _inventory = setup_trade
    modern(service, manager)
    await service.request_trade(1, "Bob")
    session = service.get_session(1)
    identity = session.session_id
    assert not (await service.confirm_trade(1, revision=0))[0]
    assert (await service.apply_action(2, identity, 0, 0, 0, 0))[0]
    assert session.revision == 1
    assert (await service.apply_action(1, identity, 1, 3, 0, 0))[0]
    assert session.initiator_confirmed
    assert (await service.apply_action(2, identity, 1, 2, 0, 20))[0]
    assert session.revision == 2
    assert not session.initiator_confirmed
    assert not session.target_confirmed
    assert not (await service.apply_action(1, identity, 1, 3, 0, 0))[0]

    snapshots = []
    for user in (1, 2):
        packet = manager.get_player_message_sender(user).connection.send.call_args.args[0]
        assert packet[:2] == bytes([252, 1])
        snapshot = json.loads(packet[4:])
        assert snapshot["viewer"] == user
        assert snapshot["revision"] == 2
        snapshots.append(snapshot["players"])
    assert snapshots[0] == snapshots[1]


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["disconnect", "reconnect", "map", "range", "death", "timeout"])
async def test_lifecycle_cancels_once_and_releases_both_users(setup_trade, event):
    service, manager, player, _inventory = setup_trade
    modern(service, manager)
    await service.request_trade(1, "Bob")
    session = service.get_session(1)
    old_sender = manager.get_player_message_sender(1)
    other = manager.get_player_message_sender(2)
    if event == "disconnect":
        del manager._users[1]
    elif event == "reconnect":
        manager.add_player(1, "Alice")
    elif event == "map":
        await player.set_position(1, 50, 50, 2)
    elif event == "range":
        await player.set_position(1, 70, 70, 1)
    elif event == "death":
        await player.redis.hset("player:1:user_stats", mapping={"min_hp": "0"})
    else:
        service.clock = lambda: 131.0
    await service.sweep()
    await service.sweep()
    assert service.get_session(1) is None
    assert service.get_session(2) is None
    assert other.connection.send.await_count == 2  # Invitación + un resultado terminal.
    assert not (await service.apply_action(1, session.session_id, 0, 3, 0, 0))[0]
    if event == "reconnect":
        assert old_sender.connection.send.await_count == 1
        assert manager.get_player_message_sender(1).init_payloads == []
    # Pueden volver a comerciar después de recuperar sus condiciones.
    manager._users[1] = (old_sender, "Alice")
    await player.set_position(1, 50, 50, 1)
    await player.redis.hset("player:1:user_stats", mapping={"min_hp": "100"})
    assert (await service.request_trade(1, "Bob"))[0]


@pytest.mark.asyncio
@pytest.mark.parametrize("commit_first", [False, True])
async def test_cancel_races_commit_without_compensation(setup_trade, commit_first):
    service, manager, player, _inventory = setup_trade
    modern(service, manager)
    await service.request_trade(1, "Bob")
    session = service.get_session(1)
    await service.apply_action(2, session.session_id, 0, 0, 0, 0)
    await service.apply_action(1, session.session_id, 1, 2, 0, 20)
    await service.apply_action(1, session.session_id, 2, 3, 0, 0)
    entered, resume = asyncio.Event(), asyncio.Event()
    original = service._perform_trade

    async def delayed(current):
        if commit_first:
            result = await original(current)
        entered.set()
        await resume.wait()
        return result if commit_first else await original(current)

    with patch.object(service, "_perform_trade", delayed):
        task = asyncio.create_task(service.apply_action(2, session.session_id, 2, 3, 0, 0))
        await asyncio.wait_for(entered.wait(), 2)
        assert (await service.cancel_trade(1, "Desconectado"))[0]
        resume.set()
        result = await task
    assert result[0] is commit_first
    assert await player.get_gold(1) == (80 if commit_first else 100)
    assert await player.get_gold(2) == (220 if commit_first else 200)
    assert not service.is_user_in_trade(1)
    assert not service.is_user_in_trade(2)
    for user in (1, 2):
        packets = [
            call.args[0]
            for call in manager.get_player_message_sender(user).connection.send.call_args_list
        ]
        assert (
            sum(
                b'"state":"completed"' in packet or b'"state":"cancelled"' in packet
                for packet in packets
            )
            == 1
        )
