"""Las etiquetas de habitantes no exponen nombres de criaturas ni pierden identidad."""

import json
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.models.npc import NPC
from src.models.npc_catalog import NPCCatalog
from src.network.msg_character import build_character_create_response
from src.services.map.player_map_service import PlayerMapService
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService


def catalog_npc(template: int) -> NPC:
    """Construye un actor con clasificación y apariencia del catálogo versionado.

    Returns:
        NPC de prueba con identidad completa.
    """
    row = NPCCatalog().get_npc_data(template)
    assert row is not None
    return NPC(
        npc_id=template,
        char_index=10001,
        instance_id=f"template-{template}",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name=str(row["nombre"]),
        description="",
        body_id=int(row["body_id"]),
        head_id=int(row["head_id"]),
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=bool(row.get("es_hostil")),
        is_attackable=bool(row.get("es_atacable")),
        role=str(row.get("role", "inhabitant")),
    )


@pytest.mark.parametrize(
    ("template", "visible"),
    [
        (500, False),
        (510, False),
        (620, False),
        (4, False),
        (17, False),
        (92, False),
        (2, True),
        (3, True),
        (5, True),
        (6, True),
        (49, True),
    ],
)
def test_catalog_nameplate_policy(template: int, visible: bool) -> None:
    """Animales neutrales y hostiles se ocultan; servicios y guardias conservan nombre."""
    npc = catalog_npc(template)
    assert npc.show_name is visible
    assert npc.name
    assert replace(npc, is_tamed=True).show_name is False
    assert replace(npc, summoned_by_user_id=1).show_name is False


@pytest.mark.parametrize("suffix", ["bat", "banker", "player"])
def test_character_create_matches_shared_golden_packet(suffix: str) -> None:
    """El byte de visibilidad es independiente del texto y de los privilegios."""
    fixtures = json.loads(
        (Path(__file__).parents[3] / "src/network/protocol/fixtures.json").read_text()
    )
    fixture = next(row for row in fixtures if row["name"] == f"character_{suffix}")
    assert build_character_create_response(
        char_index=fixture["values"]["index"],
        body=1,
        head=1,
        heading=3,
        x=50,
        y=50,
        name=fixture["values"]["name"],
        show_name=bool(fixture["values"]["show_name"]),
    ) == bytes.fromhex(fixture["hex"])


@pytest.mark.asyncio
@pytest.mark.parametrize("template", [500, 510, 4, 5, 49])
async def test_spawn_and_reconnect_send_same_policy_to_two_observers(template: int) -> None:
    """Broadcast y snapshot de entrada conservan el mismo nombre y visibilidad."""
    npc, maps = catalog_npc(template), MapManager()
    maps.add_npc(1, npc)
    observers = []
    for user in (1, 2):
        connection = MagicMock(send=AsyncMock())
        sender = MessageSender(connection)
        maps.add_player(1, user, sender)
        observers.append(sender)
    broadcast = MultiplayerBroadcastService(maps, MagicMock(), MagicMock())
    await broadcast.broadcast_character_create(
        map_id=1,
        char_index=npc.char_index,
        body=npc.body_id,
        head=npc.head_id,
        heading=3,
        x=50,
        y=50,
        name=npc.name,
    )
    service = PlayerMapService(MagicMock(), MagicMock(), maps, broadcast)
    for sender in observers:
        packet = sender.connection.send.await_args.args[0]
        assert packet[-3] == int(npc.show_name)
        assert npc.name.encode("latin1") in packet
        sender.connection.send.reset_mock()
        await service._send_npcs_in_map(1, sender)
        assert sender.connection.send.await_args.args[0] == packet
