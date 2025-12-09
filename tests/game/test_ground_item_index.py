"""Tests unitarios para GroundItemIndex."""

import asyncio

import pytest

from src.game.ground_item_index import GroundItemIndex


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
async def test_add_respects_max_and_persists() -> None:
    """Agrega items respetando límite y persiste en repo."""
    repo = DummyRepo()
    index = GroundItemIndex(max_items_per_tile=2, ground_items_repo=repo)

    index.add_ground_item(1, 1, 1, make_item(1))
    index.add_ground_item(1, 1, 1, make_item(2))
    # tercer item no entra
    index.add_ground_item(1, 1, 1, make_item(3))

    # esperar a que corran las tareas de persistencia
    await asyncio.sleep(0)

    assert index.get_ground_items(1, 1, 1) == [make_item(1), make_item(2)]
    # persistencias async se disparan (dos saves)
    assert len(repo.saved) == 2


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
