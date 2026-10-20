"""Catálogo real, prioridad de estados y equipo publicado a los dos observadores."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.command_handlers.equip_item_handler import EquipItemCommandHandler
from src.commands.equip_item_command import EquipItemCommand
from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.network.msg_character import build_character_change_response
from src.repositories.equipment_repository import EquipmentRepository
from src.services.player.appearance import PlayerAppearance, resolve_appearance
from src.services.player.player_death_service import PlayerDeathService


@pytest.mark.parametrize(
    ("item_id", "slot", "field", "graphic", "race"),
    [
        (30, "armor", "body", 22, "1"),
        (15, "weapon", "weapon", 12, "1"),
        (15, "weapon", "weapon", 48, "4"),
        (2, "weapon", "weapon", 72, "5"),
        (563, "weapon", "weapon", 20, "1"),
        (561, "weapon", "weapon", 23, "1"),
        (562, "weapon", "weapon", 74, "4"),
        (131, "helmet", "helmet", 6, "1"),
        (128, "shield", "shield", 4, "1"),
    ],
)
def test_real_catalog_uses_equipped_animation_and_race(item_id, slot, field, graphic, race):
    """GrhIndex es el icono: las capas usan Anim, NumRopaje y RazaEnanaAnim reales."""
    result = resolve_appearance(
        {"char_race": race}, {"min_hp": "1"}, {slot: "7"}, {"slot_7": f"{item_id}:1"}
    )
    assert getattr(result, field) == graphic


def test_priority_and_expiry_restore_full_equipment():
    """Fantasma/barco/mimetismo no mezclan capas; al expirar vuelve el equipo real."""
    equipment = {"armor": "1", "weapon": "2", "shield": "3", "helmet": "4"}
    inventory = {"slot_1": "30:1", "slot_2": "15:1", "slot_3": "128:1", "slot_4": "131:1"}
    assert resolve_appearance(
        {}, {"min_hp": "0", "sailing": "1"}, equipment, inventory
    ) == PlayerAppearance(500, 500)
    assert resolve_appearance({}, {"sailing": "1"}, equipment, inventory) == PlayerAppearance(84, 0)
    assert resolve_appearance(
        {},
        {"morphed_until": "9999999999", "morphed_body": "9", "morphed_head": "0"},
        equipment,
        inventory,
    ) == PlayerAppearance(9, 0)
    assert resolve_appearance({}, {"morphed_until": "1"}, equipment, inventory) == PlayerAppearance(
        22, 1, 12, 4, 6
    )
    assert resolve_appearance({}, {}, {}, inventory) == PlayerAppearance(1, 1)
    assert resolve_appearance({}, {}, {"helmet": "2"}, inventory) == PlayerAppearance(1, 1)


@pytest.mark.asyncio
async def test_equipping_replacing_and_removing_publishes_both_observers(mechanics_world):
    """El mismo handler de la UI publica Redis confirmado en ambos clientes reales de protocolo."""
    world = mechanics_world
    world.maps, world.senders = MapManager(), {}
    for user in (1, 2):
        connection = SimpleNamespace(
            send=AsyncMock(),
            address="prueba-local",
            is_authenticated=True,
            capabilities=SimpleNamespace(enabled=0),
            session_user_id=user,
        )
        world.senders[user] = MessageSender(connection)
        world.maps.add_player(2, user, world.senders[user], f"Prueba{user}")
    await world.redis.hset(
        "player:1:inventory", mapping={"slot_1": "30:1", "slot_2": "15:1", "slot_3": "563:1"}
    )
    lifecycle = PlayerDeathService(world.maps, world.player, MagicMock())
    handler = EquipItemCommandHandler(
        world.player, EquipmentRepository(world.redis), world.senders[1], lifecycle
    )
    for slot, body, weapon in [(1, 22, 0), (2, 22, 12), (3, 22, 20), (3, 22, 0), (1, 1, 0)]:
        for sender in world.senders.values():
            sender.connection.send.reset_mock()
        result = await handler.handle(EquipItemCommand(user_id=1, slot=slot))
        assert result.success
        expected = build_character_change_response(
            char_index=1, body=body, head=1, heading=2, weapon=weapon, shield=0, helmet=0
        )
        for sender in world.senders.values():
            assert expected in [call.args[0] for call in sender.connection.send.await_args_list]
