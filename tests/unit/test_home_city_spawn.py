"""La ciudad seleccionada no se sustituye por el default de Ullathorpe."""

from unittest.mock import AsyncMock

import pytest

from src.command_handlers.create_account_character_handler import CreateAccountCharacterHandler
from src.game.character_constants import JOB_ID_TO_CLASS_NAME
from src.models.city_data_loader import CityDataLoader
from src.services.game.class_service import ClassService


def test_all_protocol_homes_use_their_own_catalog_maps():
    """Las seis ciudades propias conservan sus IDs y mapas versionados."""
    assert {home: int(row["map"]) for home, row in CityDataLoader._read().items()} == {
        1: 1,
        2: 34,
        3: 59,
        4: 62,
        5: 196,
        6: 151,
    }


def test_all_twelve_protocol_classes_can_be_created():
    """Las clases ofrecidas por el cliente existen sin reemplazar su balance propio."""
    service = ClassService()
    assert {row.class_id for row in service.get_all_classes()} == set(range(1, 13))
    assert {row.class_id: row.name for row in service.get_all_classes()} == JOB_ID_TO_CLASS_NAME
    for class_id in [4, 5, 6, 7, 8, 9, 11, 12]:
        assert set(service.get_base_attributes(class_id).values()) == {10}
    assert not service.validate_class(13)


@pytest.mark.asyncio
async def test_new_character_uses_selected_home():
    """El alta consulta Redis y persiste el spawn elegido antes del login."""
    player = AsyncMock()
    player.get_position.return_value = None
    player.redis.hgetall.return_value = {"x": "44", "y": "88", "map": "34", "heading": "3"}
    await CreateAccountCharacterHandler(player).create_initial_position(42, 2)
    player.redis.hgetall.assert_awaited_once_with("world:home:2")
    player.set_position.assert_awaited_once_with(42, 44, 88, 34, 3)


@pytest.mark.asyncio
async def test_existing_position_is_never_reset():
    """Reintentar la inicialización no devuelve un personaje existente a su ciudad."""
    player = AsyncMock()
    player.get_position.return_value = {"map": 40, "x": 8, "y": 9}
    await CreateAccountCharacterHandler(player).create_initial_position(42, 2)
    player.redis.hgetall.assert_not_awaited()
    player.set_position.assert_not_awaited()
