"""El estado de maná persistido coincide con los dos paquetes que lo muestran."""

import struct
from pathlib import Path

import pytest

from src.config.game_config import GameConfig
from src.models.mana import calculate_mana
from src.network.msg_player_stats import (
    build_update_mana_response,
    build_update_user_stats_response,
)
from src.repositories.player_repository import PlayerRepository


def test_corrected_balance_with_intelligence_ten() -> None:
    """La configuración incluida deja de producir 500000 de maná inicial."""
    config = GameConfig.from_toml(Path(__file__).parents[2] / "config/server.toml")
    assert config.game.character.mana_per_int == 10
    assert calculate_mana(10, config.game.character.mana_per_int) == 100
    assert calculate_mana(100, 1000, 100) == 32767


@pytest.mark.asyncio
@pytest.mark.parametrize("maximum", [32767, 32768])
async def test_stats_validate_before_write_and_match_both_wire_messages(
    redis_client, maximum
) -> None:
    """32768 se rechaza antes de persistir; 32767 llega idéntico por ambos mensajes."""
    repository = PlayerRepository(redis_client)
    stats = {
        "max_hp": 100,
        "min_hp": 100,
        "max_mana": maximum,
        "min_mana": maximum,
        "max_sta": 100,
        "min_sta": 100,
        "gold": 0,
        "level": 1,
        "elu": 300,
        "experience": 0,
    }
    if maximum > 32767:
        with pytest.raises(ValueError, match="Maná fuera de rango"):
            await repository.set_stats(111, **stats)
        assert await repository.get_stats(111) is None
        return
    await repository.set_stats(111, **stats)
    stored = await repository.get_stats(111)
    assert stored["min_mana"] == stored["max_mana"] == maximum
    individual = build_update_mana_response(maximum)
    aggregate = build_update_user_stats_response(**stats)
    assert struct.unpack_from("<h", individual, 1)[0] == maximum
    assert struct.unpack_from("<hh", aggregate, 5) == (maximum, maximum)
    await repository.update_mana(111, maximum - 1)
    with pytest.raises(ValueError, match="Maná fuera de rango"):
        await repository.update_mana(111, 32768)
    with pytest.raises(ValueError, match="Maná fuera de rango"):
        await repository.update_mana(111, -1)
    assert (await repository.get_stats(111))["min_mana"] == maximum - 1
