"""Tests para PlayerStatsMessageSender.

Verifica el envío de estadísticas del jugador al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_player_stats_sender import PlayerStatsMessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_update_hp() -> None:
    """Verifica que send_update_hp() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_hp(hp=150)

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar estructura: PacketID + hp (int16 LE)
    assert written_data[0] == ServerPacketID.UPDATE_HP
    # hp = 150 (little-endian int16)
    assert written_data[1] == 150
    assert written_data[2] == 0

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_update_mana() -> None:
    """Verifica que send_update_mana() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_mana(mana=200)

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_MANA
    # mana = 200 (little-endian int16)
    assert written_data[1] == 200
    assert written_data[2] == 0


@pytest.mark.asyncio
async def test_send_update_strength_and_dexterity() -> None:
    """Verifica que send_update_strength_and_dexterity() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_strength_and_dexterity(strength=18, dexterity=15)

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_STRENGTH_AND_DEXTERITY
    assert written_data[1] == 18
    assert written_data[2] == 15


@pytest.mark.asyncio
async def test_send_update_strength() -> None:
    """Verifica que send_update_strength() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_strength(strength=22)

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_STRENGTH
    assert written_data[1] == 22


@pytest.mark.asyncio
async def test_send_update_dexterity() -> None:
    """Verifica que send_update_dexterity() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_dexterity(dexterity=19)

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_DEXTERITY
    assert written_data[1] == 19


@pytest.mark.asyncio
async def test_send_update_sta() -> None:
    """Verifica que send_update_sta() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_sta(stamina=180)

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_STA
    # stamina = 180 (little-endian int16)
    assert written_data[1] == 180
    assert written_data[2] == 0


@pytest.mark.asyncio
async def test_send_update_exp() -> None:
    """Verifica que send_update_exp() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_exp(experience=50000)

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_EXP
    # experience = 50000 (little-endian int32)
    assert written_data[1] == 80  # 50000 & 0xFF
    assert written_data[2] == 195  # (50000 >> 8) & 0xFF
    assert written_data[3] == 0  # (50000 >> 16) & 0xFF
    assert written_data[4] == 0  # (50000 >> 24) & 0xFF


@pytest.mark.asyncio
async def test_send_update_hunger_and_thirst() -> None:
    """Verifica que send_update_hunger_and_thirst() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_hunger_and_thirst(
        max_water=100, min_water=75, max_hunger=100, min_hunger=50
    )

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_HUNGER_AND_THIRST
    # max_water, min_water, max_hunger, min_hunger (bytes)
    assert written_data[1] == 100  # max_water
    assert written_data[2] == 75  # min_water
    assert written_data[3] == 100  # max_hunger
    assert written_data[4] == 50  # min_hunger


@pytest.mark.asyncio
async def test_send_update_user_stats() -> None:
    """Verifica que send_update_user_stats() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_user_stats(
        max_hp=200,
        min_hp=150,
        max_mana=300,
        min_mana=250,
        max_sta=180,
        min_sta=160,
        gold=10000,
        level=25,
        elu=5000,
        experience=100000,
    )

    written_data = writer.write.call_args[0][0]

    assert written_data[0] == ServerPacketID.UPDATE_USER_STATS
    # Verificar que el paquete tiene el tamaño esperado
    # PacketID (1) + max_hp (2) + min_hp (2) + max_mana (2) + min_mana (2) +
    # max_sta (2) + min_sta (2) + gold (4) + level (1) + elu (4) + experience (4) = 26 bytes
    assert len(written_data) == 26


@pytest.mark.asyncio
async def test_player_stats_message_sender_initialization() -> None:
    """Verifica que PlayerStatsMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_stats_updates() -> None:
    """Verifica que se puedan enviar múltiples actualizaciones consecutivas."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = PlayerStatsMessageSender(connection)

    await sender.send_update_hp(hp=100)
    await sender.send_update_mana(mana=50)
    await sender.send_update_sta(stamina=75)
    await sender.send_update_exp(experience=1000)

    assert writer.write.call_count == 4
    assert writer.drain.call_count == 4
