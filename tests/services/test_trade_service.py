# ruff: noqa: D102, D103, D107
"""Tests para TradeService."""

from collections import defaultdict
from unittest.mock import AsyncMock

import pytest

from src.services.trade_service import TradeService


class DummySender:
    """Mock simple de MessageSender."""

    def __init__(self) -> None:
        self.init_payloads: list[str] = []
        self.end_calls = 0
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


@pytest.fixture
def map_manager() -> DummyMapManager:
    return DummyMapManager()


@pytest.fixture
def inventory_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_slot = AsyncMock(return_value=(1, 10))
    repo.remove_item = AsyncMock(return_value=True)
    repo.add_item = AsyncMock(return_value=[(1, 1)])
    repo.remove_item_by_item_id = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def player_repo() -> AsyncMock:
    repo = AsyncMock()
    repo.get_gold = AsyncMock(return_value=0)
    repo.remove_gold = AsyncMock(return_value=True)
    repo.add_gold = AsyncMock()
    return repo


def make_service(
    player_repo: AsyncMock, inventory_repo: AsyncMock, map_manager: DummyMapManager
) -> TradeService:
    return TradeService(
        player_repo=player_repo,
        inventory_repo=inventory_repo,
        map_manager=map_manager,
    )


@pytest.mark.asyncio
async def test_request_trade_creates_session(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """Acepta solicitud cuando ambos jugadores están libres."""
    alice_sender = map_manager.add_player(1, "Alice")
    bob_sender = map_manager.add_player(2, "Bob")

    service = make_service(player_repo, inventory_repo, map_manager)

    success, message = await service.request_trade(1, "bob")

    assert success
    assert "Bob" in message
    session = service.get_session(1)
    assert session is not None
    assert session.target_id == 2
    assert service.is_user_in_trade(2)
    assert alice_sender.init_payloads == ["Bob"]
    assert bob_sender.init_payloads == ["Alice"]


@pytest.mark.asyncio
async def test_request_trade_fails_when_user_busy(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """Rechaza solicitudes si alguno ya está comerciando."""
    map_manager.add_player(1, "Alice")
    map_manager.add_player(2, "Bob")

    service = make_service(player_repo, inventory_repo, map_manager)
    await service.request_trade(1, "Bob")

    success, message = await service.request_trade(2, "Alice")

    assert not success
    assert "sesión de comercio" in message


@pytest.mark.asyncio
async def test_update_offer_item_validates_slot(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """No permite ofrecer más items de los disponibles."""
    map_manager.add_player(1, "Alice")
    map_manager.add_player(2, "Bob")
    service = make_service(player_repo, inventory_repo, map_manager)
    await service.request_trade(1, "Bob")

    inventory_repo.get_slot = AsyncMock(return_value=(42, 2))
    success, message = await service.update_offer(1, slot=1, quantity=5)

    assert not success
    assert "cantidad" in message


@pytest.mark.asyncio
async def test_cancel_trade_sends_end_packets(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """Cancelar informa a ambos jugadores."""
    alice_sender = map_manager.add_player(1, "Alice")
    bob_sender = map_manager.add_player(2, "Bob")

    service = make_service(player_repo, inventory_repo, map_manager)
    await service.request_trade(1, "Bob")

    await service.cancel_trade(1)

    assert alice_sender.end_calls == 1
    assert bob_sender.end_calls == 1


@pytest.mark.asyncio
async def test_confirm_trade_moves_items(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """Confirma intercambio moviendo items entre jugadores."""
    map_manager.add_player(1, "Alice")
    map_manager.add_player(2, "Bob")

    slots = defaultdict(dict)
    slots[1, 1] = (101, 5)
    slots[2, 2] = (202, 3)

    async def get_slot(user_id: int, slot: int):
        return slots.get((user_id, slot))

    inventory_repo.get_slot = AsyncMock(side_effect=get_slot)
    inventory_repo.remove_item = AsyncMock(return_value=True)
    inventory_repo.add_item = AsyncMock(return_value=[(5, 3)])

    service = make_service(player_repo, inventory_repo, map_manager)
    await service.request_trade(1, "Bob")
    await service.update_offer(1, slot=1, quantity=2)
    await service.update_offer(2, slot=2, quantity=1)

    result_one = await service.confirm_trade(1)
    result_two = await service.confirm_trade(2)

    assert result_one[0] is True
    assert result_two[0] is True
    inventory_repo.remove_item.assert_any_await(1, 1, 2)
    inventory_repo.remove_item.assert_any_await(2, 2, 1)
    inventory_repo.add_item.assert_any_await(2, 101, 2)
    inventory_repo.add_item.assert_any_await(1, 202, 1)


@pytest.mark.asyncio
async def test_update_offer_gold_validates_balance(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """Rechaza ofertas de oro superiores al disponible."""
    map_manager.add_player(1, "Alice")
    map_manager.add_player(2, "Bob")
    player_repo.get_gold = AsyncMock(return_value=10)

    service = make_service(player_repo, inventory_repo, map_manager)
    await service.request_trade(1, "Bob")

    success, message = await service.update_offer(1, slot=0, quantity=15)

    assert success is False
    assert "oro" in message.lower()


@pytest.mark.asyncio
async def test_confirm_trade_transfers_gold(
    map_manager: DummyMapManager, player_repo: AsyncMock, inventory_repo: AsyncMock
) -> None:
    """Transfiere oro entre jugadores cuando ambos confirman."""
    map_manager.add_player(1, "Alice")
    map_manager.add_player(2, "Bob")

    gold = {1: 100, 2: 50}

    async def get_gold(user_id: int) -> int:
        return gold[user_id]

    async def add_gold(user_id: int, amount: int) -> int:
        gold[user_id] += amount
        return gold[user_id]

    async def remove_gold(user_id: int, amount: int) -> bool:
        if gold[user_id] < amount:
            return False
        gold[user_id] -= amount
        return True

    player_repo.get_gold = AsyncMock(side_effect=get_gold)
    player_repo.add_gold = AsyncMock(side_effect=add_gold)
    player_repo.remove_gold = AsyncMock(side_effect=remove_gold)

    service = make_service(player_repo, inventory_repo, map_manager)
    await service.request_trade(1, "Bob")
    await service.update_offer(1, slot=0, quantity=40)
    await service.update_offer(2, slot=0, quantity=10)

    await service.confirm_trade(1)
    await service.confirm_trade(2)

    assert gold[1] == 100 - 40 + 10
    assert gold[2] == 50 - 10 + 40
