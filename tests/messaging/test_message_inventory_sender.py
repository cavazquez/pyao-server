"""Tests para InventoryMessageSender.

Verifica el envío de información de inventario, banco y comercio al cliente.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.messaging.senders.message_inventory_sender import InventoryMessageSender
from src.network.client_connection import ClientConnection
from src.network.packet_id import ServerPacketID


@pytest.mark.asyncio
async def test_send_change_inventory_slot() -> None:
    """Verifica que send_change_inventory_slot() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_change_inventory_slot(
        slot=1,
        item_id=100,
        name="Espada",
        amount=1,
        equipped=True,
        grh_id=500,
        item_type=1,
        max_hit=50,
        min_hit=30,
        max_def=0,
        min_def=0,
        sale_price=1000.0,
    )

    # Verificar que se llamó write
    assert writer.write.called
    written_data = writer.write.call_args[0][0]

    # Verificar que sea CHANGE_INVENTORY_SLOT
    assert written_data[0] == ServerPacketID.CHANGE_INVENTORY_SLOT
    # Verificar que el nombre esté en los datos
    name_bytes = b"Espada"
    assert name_bytes in written_data

    writer.drain.assert_called_once()


@pytest.mark.asyncio
async def test_send_change_bank_slot() -> None:
    """Verifica que send_change_bank_slot() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_change_bank_slot(
        slot=5,
        item_id=200,
        name="Poción",
        amount=10,
        grh_id=600,
        item_type=2,
        max_hit=0,
        min_hit=0,
        max_def=0,
        min_def=0,
    )

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CHANGE_BANK_SLOT
    name_bytes = "Poción".encode("latin-1")
    assert name_bytes in written_data


@pytest.mark.asyncio
async def test_send_change_npc_inventory_slot() -> None:
    """Verifica que send_change_npc_inventory_slot() construya el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_change_npc_inventory_slot(
        slot=3,
        name="Armadura",
        amount=1,
        sale_price=5000.0,
        grh_id=700,
        item_id=300,
        item_type=3,
        max_hit=0,
        min_hit=0,
        max_def=100,
        min_def=80,
    )

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CHANGE_NPC_INVENTORY_SLOT


@pytest.mark.asyncio
async def test_send_bank_init_empty() -> None:
    """Verifica que send_bank_init_empty() envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_bank_init_empty()

    written_data = writer.write.call_args[0][0]
    # Debe ser solo el PacketID
    assert len(written_data) == 1
    assert written_data[0] == ServerPacketID.BANK_INIT


@pytest.mark.asyncio
async def test_send_bank_end() -> None:
    """Verifica que send_bank_end() envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_bank_end()

    written_data = writer.write.call_args[0][0]
    assert len(written_data) == 1
    assert written_data[0] == ServerPacketID.BANK_END


@pytest.mark.asyncio
async def test_send_commerce_init_empty() -> None:
    """Verifica que send_commerce_init_empty() envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_commerce_init_empty()

    written_data = writer.write.call_args[0][0]
    assert len(written_data) == 1
    assert written_data[0] == ServerPacketID.COMMERCE_INIT


@pytest.mark.asyncio
async def test_send_commerce_end() -> None:
    """Verifica que send_commerce_end() envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_commerce_end()

    written_data = writer.write.call_args[0][0]
    assert len(written_data) == 1
    assert written_data[0] == ServerPacketID.COMMERCE_END


@pytest.mark.asyncio
async def test_send_change_spell_slot() -> None:
    """Verifica que send_change_spell_slot() construya y envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_change_spell_slot(slot=2, spell_id=50, spell_name="Apocalipsis")

    written_data = writer.write.call_args[0][0]
    assert written_data[0] == ServerPacketID.CHANGE_SPELL_SLOT
    # Verificar que el nombre del hechizo esté en los datos
    spell_name_bytes = b"Apocalipsis"
    assert spell_name_bytes in written_data


@pytest.mark.asyncio
async def test_send_meditate_toggle() -> None:
    """Verifica que send_meditate_toggle() envíe el paquete correcto."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_meditate_toggle()

    written_data = writer.write.call_args[0][0]
    assert len(written_data) == 1
    assert written_data[0] == ServerPacketID.MEDITATE_TOGGLE


@pytest.mark.asyncio
async def test_inventory_message_sender_initialization() -> None:
    """Verifica que InventoryMessageSender se inicialice correctamente."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("192.168.1.100", 54321)

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    assert sender.connection is connection


@pytest.mark.asyncio
async def test_multiple_inventory_messages() -> None:
    """Verifica que se puedan enviar múltiples mensajes consecutivos."""
    writer = MagicMock()
    writer.get_extra_info.return_value = ("127.0.0.1", 12345)
    writer.drain = AsyncMock()

    reader = MagicMock()
    connection = ClientConnection(reader, writer)
    sender = InventoryMessageSender(connection)

    await sender.send_change_inventory_slot(
        slot=1, item_id=1, name="Item1", amount=1, equipped=False, grh_id=1, item_type=1
    )
    await sender.send_bank_init_empty()
    await sender.send_bank_end()
    await sender.send_commerce_init_empty()
    await sender.send_commerce_end()

    assert writer.write.call_count == 5
    assert writer.drain.call_count == 5
