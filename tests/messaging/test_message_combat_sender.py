"""Tests para CombatMessageSender."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_combat_sender import CombatMessageSender
from src.models.body_part import BodyPart
from src.network.client_connection import ClientConnection
from src.network.packet_id import ServerPacketID


def create_mock_connection() -> tuple[ClientConnection, MagicMock]:
    """Crea una conexión mock para testing.

    Returns:
        Tupla (connection, writer) donde writer contiene los datos enviados.
    """
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)

    return connection, writer


@pytest.mark.asyncio
async def test_send_npc_hit_user_with_specific_body_part() -> None:
    """Test envío de mensaje NPCHitUser con parte del cuerpo específica."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    # Enviar mensaje con golpe en la cabeza
    await sender.send_npc_hit_user(damage=25, body_part=BodyPart.HEAD)

    # Verificar que se llamó write
    assert writer.write.called
    data = writer.write.call_args[0][0]

    # Verificar PacketID (MULTI_MESSAGE = 104)
    assert data[0] == ServerPacketID.MULTI_MESSAGE

    # Verificar índice del mensaje (NPCHitUser = 12)
    assert data[1] == 12

    # Verificar parte del cuerpo (HEAD = 1)
    assert data[2] == BodyPart.HEAD

    # Verificar daño (int16 little-endian)
    damage_bytes = int.from_bytes(data[3:5], byteorder="little", signed=True)
    assert damage_bytes == 25

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_npc_hit_user_random_body_part() -> None:
    """Test envío de mensaje NPCHitUser con parte del cuerpo aleatoria."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    # Enviar mensaje sin especificar parte del cuerpo
    await sender.send_npc_hit_user(damage=30)

    # Verificar que se llamó write
    assert writer.write.called
    data = writer.write.call_args[0][0]

    # Verificar PacketID
    assert data[0] == ServerPacketID.MULTI_MESSAGE

    # Verificar índice del mensaje (NPCHitUser = 12)
    assert data[1] == 12

    # Verificar que la parte del cuerpo es válida (1-6)
    body_part = data[2]
    assert 1 <= body_part <= 6

    # Verificar daño
    damage_bytes = int.from_bytes(data[3:5], byteorder="little", signed=True)
    assert damage_bytes == 30


@pytest.mark.asyncio
async def test_send_user_hit_npc() -> None:
    """Test envío de mensaje UserHitNPC."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    # Enviar mensaje
    await sender.send_user_hit_npc(damage=50)

    # Verificar que se llamó write
    assert writer.write.called
    data = writer.write.call_args[0][0]

    # Verificar PacketID (MULTI_MESSAGE = 104)
    assert data[0] == ServerPacketID.MULTI_MESSAGE

    # Verificar índice del mensaje (UserHitNPC = 13)
    assert data[1] == 13

    # Verificar daño (int32 little-endian)
    damage_bytes = int.from_bytes(data[2:6], byteorder="little", signed=True)
    assert damage_bytes == 50


@pytest.mark.asyncio
async def test_send_npc_hit_user_head() -> None:
    """Test método de conveniencia send_npc_hit_user_head."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    await sender.send_npc_hit_user_head(damage=15)

    data = writer.write.call_args[0][0]
    assert data[2] == BodyPart.HEAD  # Verificar que golpeó la cabeza


@pytest.mark.asyncio
async def test_send_npc_hit_user_torso() -> None:
    """Test método de conveniencia send_npc_hit_user_torso."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    await sender.send_npc_hit_user_torso(damage=20)

    data = writer.write.call_args[0][0]
    assert data[2] == BodyPart.TORSO  # Verificar que golpeó el torso


@pytest.mark.asyncio
async def test_send_npc_hit_user_left_arm() -> None:
    """Test método de conveniencia send_npc_hit_user_left_arm."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    await sender.send_npc_hit_user_left_arm(damage=12)

    data = writer.write.call_args[0][0]
    assert data[2] == BodyPart.LEFT_ARM


@pytest.mark.asyncio
async def test_send_npc_hit_user_right_arm() -> None:
    """Test método de conveniencia send_npc_hit_user_right_arm."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    await sender.send_npc_hit_user_right_arm(damage=12)

    data = writer.write.call_args[0][0]
    assert data[2] == BodyPart.RIGHT_ARM


@pytest.mark.asyncio
async def test_send_npc_hit_user_left_leg() -> None:
    """Test método de conveniencia send_npc_hit_user_left_leg."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    await sender.send_npc_hit_user_left_leg(damage=10)

    data = writer.write.call_args[0][0]
    assert data[2] == BodyPart.LEFT_LEG


@pytest.mark.asyncio
async def test_send_npc_hit_user_right_leg() -> None:
    """Test método de conveniencia send_npc_hit_user_right_leg."""
    connection, writer = create_mock_connection()
    sender = CombatMessageSender(connection)

    await sender.send_npc_hit_user_right_leg(damage=10)

    data = writer.write.call_args[0][0]
    assert data[2] == BodyPart.RIGHT_LEG


@pytest.mark.asyncio
async def test_body_part_enum_values() -> None:
    """Test que los valores del enum BodyPart son correctos."""
    assert BodyPart.HEAD == 1
    assert BodyPart.LEFT_LEG == 2
    assert BodyPart.RIGHT_LEG == 3
    assert BodyPart.RIGHT_ARM == 4
    assert BodyPart.LEFT_ARM == 5
    assert BodyPart.TORSO == 6


@pytest.mark.asyncio
async def test_send_npc_hit_user_all_body_parts() -> None:
    """Test envío de mensaje para todas las partes del cuerpo."""
    damage = 100

    for body_part in BodyPart:
        connection, writer = create_mock_connection()
        sender = CombatMessageSender(connection)

        await sender.send_npc_hit_user(damage, body_part)

        data = writer.write.call_args[0][0]
        assert data[2] == body_part
        damage_bytes = int.from_bytes(data[3:5], byteorder="little", signed=True)
        assert damage_bytes == damage
