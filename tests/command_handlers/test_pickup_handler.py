"""Tests para PickupCommandHandler.

Cubre el patrón *claim-first* introducido para cerrar la race condition de
duplicación de items en el suelo.
"""

import asyncio
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.pickup_handler import PickupCommandHandler
from src.commands.pickup_command import PickupCommand
from src.commands.walk_command import WalkCommand
from src.models.item_constants import GOLD_ITEM_ID, MAX_PLAYER_GOLD
from src.models.player_stats import PlayerStats

GroundItem = dict[str, Any]


@pytest.fixture
def mock_player_repo() -> MagicMock:
    """Mock de PlayerRepository."""
    repo = MagicMock()
    repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    repo.get_gold = AsyncMock(return_value=1000)
    repo.get_player_stats = AsyncMock(
        return_value=PlayerStats(
            max_hp=100,
            min_hp=100,
            max_mana=100,
            min_mana=100,
            max_sta=100,
            min_sta=100,
            gold=1000,
            level=1,
            elu=300,
            experience=0,
        )
    )
    repo.update_gold = AsyncMock()
    return repo


@pytest.fixture
def mock_inventory_repo() -> MagicMock:
    """Mock de InventoryRepository."""
    repo = MagicMock()
    repo.add_item = AsyncMock(return_value=[(1, 5)])
    return repo


class FakeGroundState:
    """Mini simulador de ground items para probar atomicidad.

    Modela la estructura interna: un dict ``(map_id, x, y) -> list[item]``,
    con los mismos métodos síncronos que usa el handler. Permite testear la
    race condition real: si dos coroutines llaman ``remove_ground_item`` en
    paralelo, solo una obtiene el item.
    """

    def __init__(self) -> None:
        """Crea un estado vacío (sin items en ningún tile)."""
        self._tiles: dict[tuple[int, int, int], list[GroundItem]] = {}

    def put(self, map_id: int, x: int, y: int, item: GroundItem) -> None:
        """Atajo de test: deposita un item directamente en el tile."""
        self._tiles.setdefault((map_id, x, y), []).append(item)

    def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0
    ) -> GroundItem | None:
        """Pop atómico que imita ``MapManager.remove_ground_item``."""
        items = self._tiles.get((map_id, x, y))
        if not items or item_index >= len(items):
            return None
        return items.pop(item_index)

    def add_ground_item(self, map_id: int, x: int, y: int, item: GroundItem) -> None:
        """Rollback/append como en ``MapManager.add_ground_item``."""
        self._tiles.setdefault((map_id, x, y), []).append(item)

    def get_ground_items(self, map_id: int, x: int, y: int) -> list[GroundItem]:
        """Snapshot del tile (copia) para inspección en aserciones."""
        return list(self._tiles.get((map_id, x, y), []))


@pytest.fixture
def mock_map_manager() -> MagicMock:
    """Mock de MapManager respaldado por un FakeGroundState."""
    state = FakeGroundState()
    manager = MagicMock()
    manager._state = state
    manager.get_ground_items = MagicMock(side_effect=state.get_ground_items)
    manager.remove_ground_item = MagicMock(side_effect=state.remove_ground_item)
    manager.add_ground_item = MagicMock(side_effect=state.add_ground_item)
    return manager


@pytest.fixture
def mock_broadcast_service() -> MagicMock:
    """Mock de MultiplayerBroadcastService."""
    service = MagicMock()
    service.broadcast_object_delete = AsyncMock()
    return service


@pytest.fixture
def mock_item_catalog() -> MagicMock:
    """Mock de ItemCatalog."""
    catalog = MagicMock()
    catalog.get_item_data = MagicMock(return_value={"Name": "Item Test", "GrhIndex": 100})
    return catalog


@pytest.fixture
def mock_message_sender() -> MagicMock:
    """Mock de MessageSender."""
    sender = MagicMock()
    sender.send_console_msg = AsyncMock()
    sender.send_update_user_stats = AsyncMock()
    sender.send_update_user_stats_from_repo = AsyncMock()
    sender.send_change_inventory_slot = AsyncMock()
    return sender


def _build_handler(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock | None,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock | None,
    mock_item_catalog: MagicMock | None,
    mock_message_sender: MagicMock,
) -> PickupCommandHandler:
    return PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )


@pytest.mark.asyncio
async def test_handle_no_items_on_ground(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Si el tile está vacío el handler no debe acreditar nada."""
    handler = _build_handler(
        mock_player_repo,
        mock_inventory_repo,
        mock_map_manager,
        mock_broadcast_service,
        mock_item_catalog,
        mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is False
    assert "nada aquí" in result.error_message.lower()


@pytest.mark.asyncio
async def test_handle_pickup_gold(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Pickup de oro feliz: se remueve del suelo y se suma al jugador."""
    mock_map_manager._state.put(1, 50, 50, {"item_id": GOLD_ITEM_ID, "quantity": 500})

    handler = _build_handler(
        mock_player_repo,
        mock_inventory_repo,
        mock_map_manager,
        mock_broadcast_service,
        mock_item_catalog,
        mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is True
    assert result.data["item_id"] == GOLD_ITEM_ID
    assert result.data["quantity"] == 500
    mock_player_repo.update_gold.assert_called_once_with(1, 1500)
    mock_map_manager.remove_ground_item.assert_called_once()
    assert mock_map_manager._state.get_ground_items(1, 50, 50) == []


@pytest.mark.asyncio
async def test_handle_pickup_item(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Pickup de item feliz."""
    mock_map_manager._state.put(1, 50, 50, {"item_id": 100, "quantity": 5})

    handler = _build_handler(
        mock_player_repo,
        mock_inventory_repo,
        mock_map_manager,
        mock_broadcast_service,
        mock_item_catalog,
        mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is True
    assert result.data["item_id"] == 100
    mock_inventory_repo.add_item.assert_called_once_with(1, 100, 5)
    assert mock_map_manager._state.get_ground_items(1, 50, 50) == []


@pytest.mark.asyncio
async def test_handle_invalid_command(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Un comando de otro tipo debe rechazarse limpiamente."""
    handler = _build_handler(
        mock_player_repo,
        mock_inventory_repo,
        mock_map_manager,
        mock_broadcast_service,
        mock_item_catalog,
        mock_message_sender,
    )

    result = await handler.handle(WalkCommand(user_id=1, heading=2))

    assert result.success is False


@pytest.mark.asyncio
async def test_handle_no_position(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Sin posición no se puede recoger nada (y no se toca el suelo)."""
    mock_player_repo.get_position = AsyncMock(return_value=None)

    handler = _build_handler(
        mock_player_repo,
        mock_inventory_repo,
        mock_map_manager,
        mock_broadcast_service,
        mock_item_catalog,
        mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is False
    mock_map_manager.remove_ground_item.assert_not_called()


@pytest.mark.asyncio
async def test_handle_pickup_item_full_inventory_restores_ground(
    mock_player_repo: MagicMock,
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Invariante: si el inventario está lleno, el item vuelve al suelo.

    Regresión directa del patrón claim-first: si no hicieramos rollback,
    el item se perdería tras el claim sincrónico.
    """
    mock_map_manager._state.put(1, 50, 50, {"item_id": 100, "quantity": 5})
    mock_inventory_repo.add_item = AsyncMock(return_value=[])

    handler = _build_handler(
        mock_player_repo,
        mock_inventory_repo,
        mock_map_manager,
        mock_broadcast_service,
        mock_item_catalog,
        mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is False
    assert "lleno" in result.error_message.lower()
    # El item DEBE estar de vuelta en el suelo tras el rollback.
    ground = mock_map_manager._state.get_ground_items(1, 50, 50)
    assert ground == [{"item_id": 100, "quantity": 5}]


@pytest.mark.asyncio
async def test_handle_pickup_item_without_services_restores_ground(
    mock_player_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Si faltan dependencias el item no debe desaparecer del tile."""
    mock_map_manager._state.put(1, 50, 50, {"item_id": 100, "quantity": 5})

    handler = PickupCommandHandler(
        player_repo=mock_player_repo,
        inventory_repo=None,
        map_manager=mock_map_manager,
        broadcast_service=None,
        item_catalog=None,
        party_service=None,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is False
    ground = mock_map_manager._state.get_ground_items(1, 50, 50)
    assert ground == [{"item_id": 100, "quantity": 5}]


@pytest.mark.asyncio
async def test_concurrent_pickup_does_not_duplicate_item(
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Dos pickups simultáneos sobre el mismo tile no pueden duplicar.

    Reproductor del bug original: antes del patrón claim-first, tanto
    ``get_ground_items`` como el primer ``await`` en ``add_item`` se
    completaban para las dos coroutines ANTES de que cualquiera invocara
    ``remove_ground_item``. Con el nuevo patrón solo una gana el claim.
    """
    # Dos jugadores parados en el mismo tile.
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    player_repo.get_gold = AsyncMock(return_value=0)
    player_repo.update_gold = AsyncMock()

    async def slow_add_item(_user_id: int, _item_id: int, _quantity: int) -> list[tuple[int, int]]:
        # Cede el control para maximizar el interleaving de coroutines.
        await asyncio.sleep(0)
        return [(1, 5)]

    mock_inventory_repo.add_item = AsyncMock(side_effect=slow_add_item)

    mock_map_manager._state.put(1, 50, 50, {"item_id": 100, "quantity": 5})

    handler = PickupCommandHandler(
        player_repo=player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    results = await asyncio.gather(
        handler.handle(PickupCommand(user_id=1)),
        handler.handle(PickupCommand(user_id=2)),
    )

    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    assert len(successes) == 1, "solo uno puede quedarse con el item"
    assert len(failures) == 1
    assert "nada aquí" in failures[0].error_message.lower()
    # El inventario solo se tocó una vez (el ganador).
    assert mock_inventory_repo.add_item.call_count == 1
    # El tile quedó vacío.
    assert mock_map_manager._state.get_ground_items(1, 50, 50) == []


@pytest.mark.asyncio
async def test_gold_cap_when_already_at_max(
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Si el jugador ya está en el tope, el oro se devuelve intacto al suelo."""
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    player_repo.get_gold = AsyncMock(return_value=MAX_PLAYER_GOLD)
    player_repo.update_gold = AsyncMock()

    mock_map_manager._state.put(1, 50, 50, {"item_id": GOLD_ITEM_ID, "quantity": 500})

    handler = PickupCommandHandler(
        player_repo=player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is False
    player_repo.update_gold.assert_not_called()
    ground = mock_map_manager._state.get_ground_items(1, 50, 50)
    assert ground == [{"item_id": GOLD_ITEM_ID, "quantity": 500}]


@pytest.mark.asyncio
async def test_gold_cap_partial_pickup_leaves_remainder(
    mock_inventory_repo: MagicMock,
    mock_map_manager: MagicMock,
    mock_broadcast_service: MagicMock,
    mock_item_catalog: MagicMock,
    mock_message_sender: MagicMock,
) -> None:
    """Si el pickup excede el tope, se acepta lo que entra y el resto al suelo."""
    current_gold = MAX_PLAYER_GOLD - 100
    player_repo = MagicMock()
    player_repo.get_position = AsyncMock(return_value={"map": 1, "x": 50, "y": 50})
    player_repo.get_gold = AsyncMock(return_value=current_gold)
    player_repo.update_gold = AsyncMock()

    mock_map_manager._state.put(1, 50, 50, {"item_id": GOLD_ITEM_ID, "quantity": 500})

    handler = PickupCommandHandler(
        player_repo=player_repo,
        inventory_repo=mock_inventory_repo,
        map_manager=mock_map_manager,
        broadcast_service=mock_broadcast_service,
        item_catalog=mock_item_catalog,
        party_service=None,
        message_sender=mock_message_sender,
    )

    result = await handler.handle(PickupCommand(user_id=1))

    assert result.success is True
    assert result.data["quantity"] == 100
    player_repo.update_gold.assert_called_once_with(1, MAX_PLAYER_GOLD)
    # Quedan 400 monedas en el suelo.
    ground = mock_map_manager._state.get_ground_items(1, 50, 50)
    assert len(ground) == 1
    assert ground[0]["quantity"] == 400
    assert ground[0]["item_id"] == GOLD_ITEM_ID
