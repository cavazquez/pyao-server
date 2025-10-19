"""Tests para msg_player_stats.py."""

from src.msg_player_stats import (
    build_update_exp_response,
    build_update_hp_response,
    build_update_hunger_and_thirst_response,
    build_update_mana_response,
    build_update_sta_response,
    build_update_user_stats_response,
)
from src.packet_id import ServerPacketID


def test_build_update_hp_response() -> None:
    """Verifica que build_update_hp_response construye el paquete correctamente."""
    response = build_update_hp_response(hp=150)

    assert isinstance(response, bytes)
    assert len(response) == 3  # 1 byte PacketID + 2 bytes int16
    assert response[0] == ServerPacketID.UPDATE_HP


def test_build_update_mana_response() -> None:
    """Verifica que build_update_mana_response construye el paquete correctamente."""
    response = build_update_mana_response(mana=200)

    assert isinstance(response, bytes)
    assert len(response) == 3
    assert response[0] == ServerPacketID.UPDATE_MANA


def test_build_update_sta_response() -> None:
    """Verifica que build_update_sta_response construye el paquete correctamente."""
    response = build_update_sta_response(stamina=100)

    assert isinstance(response, bytes)
    assert len(response) == 3
    assert response[0] == ServerPacketID.UPDATE_STA


def test_build_update_exp_response() -> None:
    """Verifica que build_update_exp_response construye el paquete correctamente."""
    response = build_update_exp_response(experience=5000)

    assert isinstance(response, bytes)
    assert len(response) == 5  # 1 byte PacketID + 4 bytes int32
    assert response[0] == ServerPacketID.UPDATE_EXP


def test_build_update_hunger_and_thirst_response() -> None:
    """Verifica que build_update_hunger_and_thirst_response construye el paquete correctamente."""
    response = build_update_hunger_and_thirst_response(
        max_water=100, min_water=50, max_hunger=100, min_hunger=75
    )

    assert isinstance(response, bytes)
    assert len(response) == 5  # 1 byte PacketID + 4 bytes
    assert response[0] == ServerPacketID.UPDATE_HUNGER_AND_THIRST


def test_build_update_user_stats_response() -> None:
    """Verifica que build_update_user_stats_response construye el paquete correctamente."""
    response = build_update_user_stats_response(
        max_hp=200,
        min_hp=150,
        max_mana=100,
        min_mana=80,
        max_sta=100,
        min_sta=90,
        gold=1000,
        level=5,
        elu=500,
        experience=2000,
    )

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.UPDATE_USER_STATS
    # 1 byte PacketID + 6*2 bytes (stats) + 4 bytes (gold) + 1 byte (level)
    # + 4 bytes (elu) + 4 bytes (exp)
    assert len(response) == 1 + 12 + 4 + 1 + 4 + 4
