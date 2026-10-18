"""Tests unitarios para GroundItemIndex."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.game.ground_item_index import GroundItemIndex


@pytest.mark.asyncio
@pytest.mark.parametrize("update", ["load", "commit"])
async def test_snapshot_orders_concurrent_load_or_commit_after_visible_objects(update):
    """El suelo inicial precede a la siguiente carga/commit y usa el stack visible."""
    index = GroundItemIndex(max_items_per_tile=3)
    index.add_ground_item(1, 1, 1, {"grh_index": 100})
    index.add_ground_item(1, 1, 1, {"grh_index": 999})
    index.add_ground_item(1, 2, 2, {"grh_index": 101})
    index.add_ground_item(2, 3, 3, {"grh_index": 900})
    started, release = asyncio.Event(), asyncio.Event()
    stream = []

    async def send_object(x, y, graphic):
        stream.append((x, y, graphic))
        if len(stream) == 1:
            started.set()
            await release.wait()

    snapshot = asyncio.create_task(index.send_snapshot(1, send_object))
    await started.wait()
    if update == "load":
        repository = DummyRepo()
        repository.to_load[1] = {(3, 3): [{"grh_index": 102}]}
        index.ground_items_repo = repository
        changed = asyncio.create_task(index.load_ground_items(1))
    else:
        changed = asyncio.create_task(
            index.add_committed(1, 3, 3, {"item_id": 1, "quantity": 1, "grh_index": 102}, None)
        )
    await asyncio.sleep(0)
    assert not changed.done()
    release.set()
    assert await snapshot == 2
    await changed
    assert stream == [(1, 1, 100), (2, 2, 101)]
    assert index.get_ground_items(1, 3, 3)[0]["grh_index"] == 102
    assert index.get_ground_items(2, 3, 3)[0]["grh_index"] == 900


@pytest.mark.asyncio
async def test_cancelled_snapshot_does_not_keep_map_locked():
    """Cancelar el envío permite continuar una operación posterior del mapa."""
    index = GroundItemIndex(max_items_per_tile=3)
    index.add_ground_item(1, 1, 1, {"grh_index": 100})
    started, release = asyncio.Event(), asyncio.Event()

    async def send_object(_x, _y, _graphic):
        started.set()
        await release.wait()

    snapshot = asyncio.create_task(index.send_snapshot(1, send_object))
    await started.wait()
    snapshot.cancel()
    with pytest.raises(asyncio.CancelledError):
        await snapshot
    assert await asyncio.wait_for(
        index.add_committed(1, 2, 2, {"item_id": 1, "quantity": 1}, None), timeout=1
    )
    assert await index.send_snapshot(2, AsyncMock()) == 0


class DummyRepo:
    """Repo simulada para validar persistencia."""

    def __init__(self) -> None:
        """Inicializa el almacenamiento simulado."""
        self.saved: list[tuple[int, dict[tuple[int, int], list[dict[str, int | str | None]]]]] = []
        self.to_load: dict[int, dict[tuple[int, int], list[dict[str, int | str | None]]]] = {}

    async def save_ground_items(
        self, map_id: int, items: dict[tuple[int, int], list[dict[str, int | str | None]]]
    ) -> None:
        """Guarda items simuladamente."""
        self.saved.append((map_id, items))

    async def load_ground_items(
        self, map_id: int
    ) -> dict[tuple[int, int], list[dict[str, int | str | None]]]:
        """Carga items simuladamente."""
        return self.to_load.get(map_id, {})


def make_item(idx: int) -> dict[str, int]:
    """Crea un item simple de prueba."""
    return {"item_id": idx, "quantity": 1}


@pytest.mark.asyncio
async def test_memory_api_respects_capacity_and_rejects_persistent_snapshots() -> None:
    """La API síncrona de tests no puede reintroducir persistencias ciegas en producción."""
    index = GroundItemIndex(max_items_per_tile=2)
    index.add_ground_item(1, 1, 1, make_item(1))
    index.add_ground_item(1, 1, 1, make_item(2))
    index.add_ground_item(1, 1, 1, make_item(3))
    assert index.get_ground_items(1, 1, 1) == [make_item(1), make_item(2)]
    persistent = GroundItemIndex(max_items_per_tile=2, ground_items_repo=DummyRepo())
    with pytest.raises(RuntimeError, match="commit"):
        persistent.add_ground_item(1, 1, 1, make_item(1))
    with pytest.raises(RuntimeError, match="commit"):
        await persistent.persist_ground_items(1)


@pytest.mark.asyncio
async def test_remove_and_clear() -> None:
    """Remueve items y limpia conteo."""
    index = GroundItemIndex(max_items_per_tile=2)
    index.add_ground_item(1, 1, 1, make_item(1))
    index.add_ground_item(1, 2, 2, make_item(2))

    removed = index.remove_ground_item(1, 1, 1, 0)
    assert removed == make_item(1)
    assert index.get_ground_items(1, 1, 1) == []

    count = index.clear_ground_items(1)
    assert count == 1  # solo quedaba el item en (2,2)
    assert index.get_ground_items_count(1) == 0


@pytest.mark.asyncio
async def test_load_ground_items() -> None:
    """Carga items desde repo simulado."""
    repo = DummyRepo()
    repo.to_load[1] = {(1, 1): [make_item(1)], (2, 2): [make_item(2), make_item(3)]}
    index = GroundItemIndex(max_items_per_tile=3, ground_items_repo=repo)

    await index.load_ground_items(1)

    assert index.get_ground_items_count(1) == 3
    assert index.get_ground_items(1, 1, 1) == [make_item(1)]
    assert index.get_ground_items(1, 2, 2) == [make_item(2), make_item(3)]
