"""Tests para msg_inventory.py."""

from src.msg_inventory import (
    build_change_bank_slot_response,
    build_change_inventory_slot_response,
    build_change_npc_inventory_slot_response,
    build_change_spell_slot_response,
    build_commerce_end_response,
    build_commerce_init_response,
    build_pong_response,
)
from src.packet_id import ServerPacketID


def test_build_change_inventory_slot_response() -> None:
    """Verifica que build_change_inventory_slot_response construye el paquete correctamente."""
    response = build_change_inventory_slot_response(
        slot=1,
        item_id=100,
        name="Espada",
        amount=1,
        equipped=True,
        grh_id=500,
        item_type=2,
        max_hit=10,
        min_hit=5,
        max_def=0,
        min_def=0,
        sale_price=100.0,
    )

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CHANGE_INVENTORY_SLOT


def test_build_change_bank_slot_response() -> None:
    """Verifica que build_change_bank_slot_response construye el paquete correctamente."""
    response = build_change_bank_slot_response(
        slot=1,
        item_id=50,
        name="Poción",
        amount=10,
        grh_id=300,
        item_type=1,
        max_hit=0,
        min_hit=0,
        max_def=0,
        min_def=0,
    )

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CHANGE_BANK_SLOT


def test_build_change_npc_inventory_slot_response() -> None:
    """Verifica que build_change_npc_inventory_slot_response construye el paquete correctamente."""
    response = build_change_npc_inventory_slot_response(
        slot=1,
        name="Item",
        amount=5,
        sale_price=50.0,
        grh_id=200,
        item_id=25,
        item_type=1,
        max_hit=0,
        min_hit=0,
        max_def=0,
        min_def=0,
    )

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CHANGE_NPC_INVENTORY_SLOT


def test_build_change_spell_slot_response() -> None:
    """Verifica que build_change_spell_slot_response construye el paquete correctamente."""
    response = build_change_spell_slot_response(slot=1, spell_id=10, spell_name="Apocalipsis")

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.CHANGE_SPELL_SLOT


def test_build_commerce_end_response() -> None:
    """Verifica que build_commerce_end_response construye el paquete correctamente."""
    response = build_commerce_end_response()

    assert isinstance(response, bytes)
    assert len(response) == 1
    assert response[0] == ServerPacketID.COMMERCE_END


def test_build_commerce_init_response() -> None:
    """Verifica que build_commerce_init_response construye el paquete correctamente."""
    items = [
        (1, 100, "Espada", 1, 500, 1000, 2, 10, 5, 0, 0),
        (2, 101, "Escudo", 1, 300, 1001, 3, 0, 0, 5, 3),
    ]
    response = build_commerce_init_response(npc_id=2, items=items)

    assert isinstance(response, bytes)
    assert response[0] == ServerPacketID.COMMERCE_INIT


def test_build_pong_response() -> None:
    """Verifica que build_pong_response construye el paquete correctamente."""
    response = build_pong_response()

    assert isinstance(response, bytes)
    assert len(response) == 1
    assert response[0] == ServerPacketID.PONG
