"""Protocolo real y publicaciones de habilidades sobre repositorios Redis reales."""

import asyncio
import json
import struct
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from src.combat.combat_critical_calculator import CriticalCalculator
from src.command_handlers.meditate_handler import MeditateCommandHandler
from src.command_handlers.walk_validation_handler import WalkValidationHandler
from src.command_handlers.work_handler import WorkCommandHandler
from src.commands.meditate_command import MeditateCommand
from src.commands.work_command import WorkCommand
from src.effects.meditation_effect import MeditationEffect
from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.models.spell_catalog import SpellCatalog
from src.network.capabilities import SUPPORTED_CAPABILITIES
from src.network.msg_visual_effects import build_create_fx_response
from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID
from src.services.action_cadence import ActionCadence
from src.services.combat.combat_service import CombatService
from src.services.combat.physical_plan import (
    PhysicalPlan,
    PhysicalRequest,
    commit_physical,
    defend_npc,
)
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.services.npc.npc_ai_service import NPCAIService
from src.services.player.spell_service import SpellService
from src.services.skill_action_service import SkillActionService
from src.tasks.task_skill_action import TaskSkillAction
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def action_world(mechanics_world):
    """Conserva servidor, protocolo y mensajes reales; reemplaza sólo transporte/AOF.

    Yields:
        Mundo de dos observadores con cadencia controlable y paquetes capturados.
    """
    world = mechanics_world
    maps = MapManager()
    world.senders = {}
    for uid in (1, 2):
        connection = SimpleNamespace(
            send=AsyncMock(),
            address="prueba-local",
            is_authenticated=True,
            capabilities=SimpleNamespace(enabled=SUPPORTED_CAPABILITIES),
            state_epoch=f"{uid:032x}",
            state_sequence=0,
            session_redis=None,
            session_user_id=uid,
        )
        sender = MessageSender(connection)
        world.senders[uid] = sender
        maps.add_player(2, uid, sender, f"Prueba{uid}")
        maps.update_player_tile(uid, 2, 0, 0, 50, 49 + uid)
    maps.add_npc(2, world.npc)
    clock = [0.0]
    service = SkillActionService(
        world.player,
        world.inventory,
        world.terrain,
        maps,
        world.catalog,
        SimpleNamespace(npc_repository=world.npcs),
        SimpleNamespace(handle_npc_death=AsyncMock()),
        SimpleNamespace(publish_state=AsyncMock(), schedule_death=MagicMock()),
        ActionCadence(clock=lambda: clock[0]),
    )
    world.maps, world.actions, world.clock = maps, service, clock
    with patch("src.services.skill_action_service.require_durable", new=AsyncMock()):
        yield world


@pytest.mark.asyncio
async def test_boat_confirmation_waits_for_durability_before_enabling_walk(action_world):
    """La apariencia y el toggle no adelantan al cliente durante WAITAOF."""
    world = action_world
    world.terrain.has_water = lambda _map, x, _y: x > 50
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "474:1")
    await world.redis.hset(RedisKeys.player_skills(1), "level:navegacion", "100")
    entered, release = asyncio.Event(), asyncio.Event()
    calls = 0

    async def durable(_redis):
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            await release.wait()

    with patch("src.services.skill_action_service.require_durable", new=durable):
        task = asyncio.create_task(
            world.actions.execute(1, "navigate", {"slot": 1}, world.senders[1])
        )
        await asyncio.wait_for(entered.wait(), 1)
        try:
            assert await world.redis.hget(RedisKeys.player_user_stats(1), "sailing") == "1"
            world.actions.player_death.publish_state.assert_not_awaited()
            assert not world.senders[1].connection.send.await_args_list
        finally:
            release.set()
            result = await task
    assert result["sailing"] is True
    world.actions.player_death.publish_state.assert_awaited_once_with(1)
    frames = [call.args[0] for call in world.senders[1].connection.send.await_args_list]
    assert frames[-1] == bytes([ServerPacketID.NAVIGATE_TOGGLE])


@pytest.mark.asyncio
async def test_front_work_executes_the_same_atomic_action_as_target_work(action_world):
    """TaskWork sobre un recurso frontal no se queda solicitando otro cursor."""
    world = action_world
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "127:1")
    await world.redis.hset(RedisKeys.player_equipment(1), "weapon", "1")
    handler = WorkCommandHandler(
        world.player, world.inventory, world.terrain, world.senders[1], skill_actions=world.actions
    )
    with patch("src.services.gathering.random.random", return_value=0.0):
        result = await handler.handle(WorkCommand(1, 2, 49, 50, skill_type=9))
    assert result.success is True
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:talar") == "50"


@pytest.mark.asyncio
async def test_real_npc_ai_routes_damage_and_training_through_atomic_defense(action_world):
    """IA, combate, repositorios y mensajes reales consumen un solo turno del NPC."""
    world = action_world
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "404:1")
    await world.redis.hset(RedisKeys.player_equipment(1), "shield", "1")
    combat = CombatService(world.player, world.npcs, None, world.inventory, world.catalog)
    broadcast = MultiplayerBroadcastService(world.maps, world.player, AsyncMock())
    ai = NPCAIService(
        SimpleNamespace(), world.maps, world.player, combat, broadcast, SimpleNamespace()
    )
    with patch("src.services.combat.physical_plan.random.random", return_value=0.99):
        assert await ai.try_attack_player(world.npc, 1) is True
        assert await ai.try_attack_player(world.npc, 1) is False
    stats = await world.redis.hgetall(RedisKeys.player_user_stats(1))
    assert int(stats["min_hp"]) < 500
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:tacticas") == "20"
    assert await world.redis.hget(RedisKeys.player_skills(1), "xp:defensa") == "20"
    packets = [call.args[0][0] for call in world.senders[1].connection.send.await_args_list]
    assert ServerPacketID.UPDATE_USER_STATS in packets


@pytest.mark.asyncio
@pytest.mark.parametrize("spell", [18, 19, 20, 21])
async def test_actual_attribute_spells_change_physical_combat_until_expiration(action_world, spell):
    """Celeridad/Torpeza y Fuerza/Debilidad actúan en combate sin mutar atributos base."""
    world = action_world
    attribute = "agility" if spell in {18, 19} else "strength"
    await world.redis.hset(RedisKeys.player_skills(2), "level:magia", "100")
    await world.redis.hset(RedisKeys.player_spellbook(2), str(spell), str(spell))
    await world.redis.hset(
        RedisKeys.player_user_stats(2), mapping={"min_mana": "5000", "max_mana": "5000"}
    )
    service = SpellService(
        SpellCatalog(), world.player, world.npcs, world.maps, item_catalog=world.catalog
    )

    async def attack():
        if attribute == "strength":
            with patch(
                "src.services.combat.physical_plan.random.random",
                side_effect=[0.0, 0.99, 0.99, 0.5, 0.99],
            ):
                plan = PhysicalPlan(PhysicalRequest(1, target_npc="animal"), world.catalog, 30, 20)
            return await commit_physical(world.redis.redis, plan, operation_id())
        await world.redis.hset(RedisKeys.npc_instance("animal"), "last_attack_time", "0")
        with patch(
            "src.services.combat.physical_plan.random.random",
            side_effect=[
                CriticalCalculator().calculate_dodge_chance(20)
                + (0.005 if spell == 18 else -0.005),
                0.99,
            ],
        ):
            return await defend_npc(
                world.redis.redis, 1, "animal", world.catalog, 100, operation_id()
            )

    before = await attack()
    with patch("src.services.combat.spell_plan.require_durable", new=AsyncMock()):
        assert await service.cast_spell(2, spell, 50, 50, world.senders[2], slot=spell)
    active = await attack()
    await world.redis.hset(RedisKeys.player_stats(1), f"{attribute}_modifier_until", "1")
    expired = await attack()
    assert await world.redis.hget(RedisKeys.player_stats(1), attribute) == "20"
    if spell == 18:
        assert before["damage"] > 0
        assert active["damage"] == 0
    elif spell == 19:
        assert before["damage"] == 0
        assert active["damage"] > 0
    elif spell == 20:
        assert active["damage"] > before["damage"]
    else:
        assert active["damage"] < before["damage"]
    assert expired["damage"] == before["damage"]


def wire_request(action, params, identity=None):
    """Construye bytes de un pedido, independiente del parser de la tarea.

    Returns:
        Packet 251 versión 1 con JSON Latin-1 limitado por el contrato.
    """
    return (
        PacketBuilder()
        .add_byte(251)
        .add_byte(1)
        .add_unicode_string(
            json.dumps({"id": identity or operation_id(), "action": action, "params": params})
        )
        .to_bytes()
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("skill", ["herreria", "carpinteria", "mineria"])
async def test_recipe_pagination_through_negotiated_task_fits_packet_limit(action_world, skill):
    """La consulta real entrega nombres y páginas que caben en el framer del cliente."""
    world = action_world
    sender = world.senders[1]
    identity = operation_id()
    task = TaskSkillAction(
        wire_request("recipes", {"skill": skill, "page": 0}, identity),
        sender,
        world.actions,
        {"user_id": 1},
    )
    await task.execute()
    packet = sender.connection.send.await_args.args[0]
    assert packet[0] == ServerPacketID.SKILL_ACTION_STATE
    assert len(packet) <= 3804
    size = int.from_bytes(packet[2:4], "little")
    result = json.loads(packet[4 : 4 + size].decode("latin-1"))
    assert result["id"] == identity
    assert result["applied"] is True
    assert 1 <= len(result["recipes"]) <= 4
    assert result["recipes"][0]["materials"][0]["name"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case",
    [
        "unauthenticated",
        "unnegotiated",
        "unknown_field",
        "boolean_quantity",
        "oversized",
        "trailing",
        "version",
    ],
)
async def test_untrusted_action_never_mutates_or_trains(action_world, case):
    """Autenticación, negociación, esquema, tipos y tamaños se validan antes de operar."""
    world = action_world
    sender = world.senders[1]
    packet = wire_request("hide", {})
    if case == "unauthenticated":
        sender.connection.is_authenticated = False
    elif case == "unnegotiated":
        sender.connection.capabilities.enabled = 0
    elif case == "unknown_field":
        packet = wire_request("hide", {"level": 100})
    elif case == "boolean_quantity":
        packet = wire_request("craft", {"recipe": "carpinteria:480", "quantity": True})
    elif case == "oversized":
        packet = wire_request("craft", {"recipe": "x" * 1100, "quantity": 1})
    elif case == "trailing":
        packet += b"x"
    elif case == "version":
        packet = bytes([251, 2]) + packet[2:]
    before = await world.redis.hgetall(RedisKeys.player_skills(1))
    await TaskSkillAction(packet, sender, world.actions, {"user_id": 1}).execute()
    assert await world.redis.hgetall(RedisKeys.player_skills(1)) == before
    assert sender.connection.send.await_count == 0


@pytest.mark.asyncio
async def test_work_through_service_updates_inventory_progress_and_peer_fx(action_world):
    """El mismo servicio confirma el recurso y publica progreso antes de su respuesta."""
    world = action_world
    await world.redis.hset(RedisKeys.player_inventory(1), "slot_1", "127:1")
    await world.redis.hset(RedisKeys.player_equipment(1), "weapon", "1")
    identity = operation_id()
    with patch("src.services.gathering.random.random", return_value=0.0):
        first = await world.actions.execute(
            1, "work", {"skill": 9, "x": 51, "y": 50}, world.senders[1], identity=identity
        )
        rejected = await world.actions.execute(
            1, "work", {"skill": 9, "x": 51, "y": 50}, world.senders[1]
        )
        world.clock[0] += 1
        replay = await world.actions.execute(
            1, "work", {"skill": 9, "x": 51, "y": 50}, world.senders[1], identity=identity
        )
    assert first == replay
    assert rejected["applied"] is False
    assert await world.inventory.get_slot(1, 2) == (58, 5)
    assert any(
        c.args[0][0] == ServerPacketID.SKILL_CATALOG
        for c in world.senders[1].connection.send.await_args_list
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("water", [True, False])
async def test_ranged_service_uses_actual_actor_for_all_observers_and_respects_wall(
    action_world, water
):
    """Los dos observadores reciben efecto sobre el NPC real; una pared impide el disparo."""
    world = action_world
    world.terrain.has_water = lambda _map, x, _y: water and x == 52
    world.terrain.is_blocked = lambda _map, x, _y: water and x == 52
    await world.redis.hset(
        RedisKeys.player_inventory(1), mapping={"slot_1": "665:1", "slot_2": "480:3"}
    )
    await world.redis.hset(RedisKeys.player_equipment(1), "weapon", "1")
    world.maps.remove_npc(2, "animal")
    world.npc.x = 53
    world.maps.add_npc(2, world.npc)
    await world.redis.hset(RedisKeys.npc_instance("animal"), "x", "53")
    with patch(
        "src.services.combat.physical_plan.random.random", side_effect=[0.0, 0.99, 0.99, 0.5, 0.99]
    ):
        result = await world.actions.execute(
            1, "work", {"skill": 18, "x": 53, "y": 50}, world.senders[1]
        )
    assert result["damage"] > 0
    for sender in world.senders.values():
        fx = [
            c.args[0]
            for c in sender.connection.send.await_args_list
            if c.args[0][0] == ServerPacketID.CREATE_FX
        ]
        assert any(int.from_bytes(p[1:3], "little") == 10001 for p in fx)
        assert any(
            c.args[0][0] == ServerPacketID.PLAY_WAVE for c in sender.connection.send.await_args_list
        )
    world.clock[0] += 1
    world.terrain.has_water = lambda *_: False
    world.terrain.is_blocked = lambda _m, x, _y: x == 52
    second = await world.actions.execute(
        1, "work", {"skill": 18, "x": 53, "y": 50}, world.senders[1]
    )
    assert second["applied"] is False
    assert await world.inventory.get_slot(1, 2) == (480, 2)


@pytest.mark.asyncio
async def test_visibility_magic_hiding_expiry_and_recreated_actor(action_world):
    """El dueño y su observador recuperan invisibilidad, revelación y recreación de actor."""
    world = action_world
    key = RedisKeys.player_user_stats(1)
    await world.redis.hset(key, mapping={"invisible_until": "200", "hidden_until": "150"})
    with patch("src.messaging.senders.message_status_effects_sender.time.time", return_value=100):
        for viewer, sender in world.senders.items():
            await sender.status_effects.sync_visibility(viewer, world.player, world.maps)
            packet = next(
                c.args[0]
                for c in sender.connection.send.await_args_list
                if c.args[0][0] == ServerPacketID.SET_INVISIBLE
                and int.from_bytes(c.args[0][1:3], "little") == 1
            )
            assert packet[-1] == 1
        await world.redis.hset(key, "hidden_until", "0")
        world.senders[2].status_effects.invalidate_character(1)
        await world.senders[2].status_effects.sync_visibility(2, world.player, world.maps)
        assert world.senders[2].connection.send.await_args.args[0][-1] == 1
    with patch("src.messaging.senders.message_status_effects_sender.time.time", return_value=201):
        for viewer, sender in world.senders.items():
            await sender.status_effects.sync_visibility(viewer, world.player, world.maps)
            assert sender.connection.send.await_args.args[0] == struct.pack(
                "<BhB", ServerPacketID.SET_INVISIBLE, 1, 0
            )


@pytest.mark.asyncio
async def test_campfire_is_visible_to_peers_and_removed_when_expired(action_world):
    """La fogata usa un objeto real del mapa y desaparece al expirar su clave Redis."""
    world = action_world
    await world.redis.hset("world:campfire:2:49:50", mapping={"until": "200", "x": "49", "y": "50"})
    await world.redis.sadd("world:campfires:2", "world:campfire:2:49:50")
    with patch("src.messaging.senders.message_status_effects_sender.time.time", return_value=100):
        for uid, sender in world.senders.items():
            await sender.status_effects.sync_campfires(uid, world.player)
            assert sender.connection.send.await_args.args[0] == struct.pack(
                "<BBBh", ServerPacketID.OBJECT_CREATE, 49, 50, 1521
            )
        await world.redis.redis.delete("world:campfire:2:49:50")
        for uid, sender in world.senders.items():
            await sender.status_effects.sync_campfires(uid, world.player)
            assert sender.connection.send.await_args.args[0] == bytes(
                [ServerPacketID.OBJECT_DELETE, 49, 50]
            )


@pytest.mark.asyncio
async def test_campfire_concurrent_sync_and_map_reentry_are_idempotent(action_world):
    """Ticks concurrentes no duplican objetos; volver al mapa reconstruye la vista."""
    world = action_world
    await world.redis.hset("world:campfire:2:49:50", mapping={"until": "200", "x": "49", "y": "50"})
    await world.redis.sadd("world:campfires:2", "world:campfire:2:49:50")
    sender = world.senders[1].status_effects
    with patch("src.messaging.senders.message_status_effects_sender.time.time", return_value=100):
        await asyncio.gather(*(sender.sync_campfires(1, world.player) for _ in range(5)))
        create = struct.pack("<BBBh", ServerPacketID.OBJECT_CREATE, 49, 50, 1521)
        assert [call.args[0] for call in world.senders[1].connection.send.await_args_list].count(
            create
        ) == 1
        await world.player.set_position(1, 50, 50, 1, 3)
        await sender.sync_campfires(1, world.player)
        assert sender._campfires == set()
        await world.player.set_position(1, 50, 50, 2, 3)
        await sender.sync_campfires(1, world.player)
        assert sender._campfires == {(49, 50)}
        assert [call.args[0] for call in world.senders[1].connection.send.await_args_list].count(
            create
        ) == 2


@pytest.mark.asyncio
async def test_meditation_reaches_peer_and_recreated_actor_without_restarting(action_world):
    """El actor, su observador y una conexión nueva ven el mismo efecto continuo."""
    world = action_world
    handler = MeditateCommandHandler(world.player, world.senders[1])
    result = await handler.handle(MeditateCommand(user_id=1))
    assert result.success
    start = build_create_fx_response(1, 16, -1)
    for viewer, sender in world.senders.items():
        await sender.status_effects.sync_visibility(viewer, world.player, world.maps)
        packets = [call.args[0] for call in sender.connection.send.await_args_list]
        assert packets.count(start) == 1
        assert packets.count(bytes([ServerPacketID.MEDITATE_TOGGLE])) == (viewer == 1)
        sender.connection.send.reset_mock()
        await asyncio.gather(
            sender.status_effects.sync_visibility(viewer, world.player, world.maps),
            sender.status_effects.sync_visibility(viewer, world.player, world.maps),
        )
        sender.connection.send.assert_not_awaited()
    observer = world.senders[2]
    await observer.send_character_create(1, 1, 1, 1, 50, 50)
    await observer.status_effects.sync_visibility(2, world.player, world.maps)
    assert observer.connection.send.await_args.args[0] == start
    observer.connection.send.reset_mock()
    reconnected = MessageSender(observer.connection)
    await reconnected.status_effects.sync_visibility(2, world.player, world.maps)
    assert start in [call.args[0] for call in observer.connection.send.await_args_list]


@pytest.mark.asyncio
@pytest.mark.parametrize("reason", ["manual", "movement", "full_mana", "death"])
async def test_meditation_stops_for_every_observer(action_world, reason):
    """Las cancelaciones y estados vitales retiran el aura sin togglear al observador."""
    world = action_world
    key = RedisKeys.player_user_stats(1)
    handler = MeditateCommandHandler(world.player, world.senders[1])
    await handler.handle(MeditateCommand(user_id=1))
    for viewer, sender in world.senders.items():
        await sender.status_effects.sync_visibility(viewer, world.player, world.maps)
        sender.connection.send.reset_mock()
    if reason == "manual":
        await handler.handle(MeditateCommand(user_id=1))
    elif reason == "movement":
        walk = WalkValidationHandler(world.player, None, world.senders[1])
        await walk._cancel_meditation_if_active(1)
    elif reason == "full_mana":
        await world.redis.hset(key, mapping={"min_mana": "100", "max_mana": "100"})
        await MeditationEffect().apply(1, world.player, world.senders[1])
    else:
        await world.redis.hset(key, "min_hp", "0")
    for viewer, sender in world.senders.items():
        await sender.sync_status(viewer, world.player)
        await sender.status_effects.sync_visibility(viewer, world.player, world.maps)
        packets = [call.args[0] for call in sender.connection.send.await_args_list]
        assert packets.count(build_create_fx_response(1, 0, 0)) == 1
        if viewer == 2:
            assert bytes([ServerPacketID.MEDITATE_TOGGLE]) not in packets
        sender.connection.send.reset_mock()
        await sender.status_effects.sync_visibility(viewer, world.player, world.maps)
        sender.connection.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_meditation_chat_reports_only_confirmed_recovery(action_world):
    """El chat refleja el maná confirmado sin inventar recuperaciones en ticks vacíos."""
    world = action_world
    key = RedisKeys.player_user_stats(1)
    await world.redis.hset(
        key, mapping={"meditating": "1", "meditation_due": "1", "min_mana": "95", "max_mana": "100"}
    )
    with patch("src.services.meditation.random.random", return_value=0.0):
        await MeditationEffect().apply(1, world.player, world.senders[1])
    assert await world.redis.hget(key, "min_mana") == "100"
    packets = [call.args[0] for call in world.senders[1].connection.send.await_args_list]
    messages = [
        json.loads(packet[4:].decode("ascii"))["data"]["text"]
        for packet in packets
        if packet[0] == ServerPacketID.WORLD_STATE
        and json.loads(packet[4:].decode("ascii"))["kind"] == "chat"
    ]
    assert "Meditando recuperas 5 puntos de maná (maná actual: 100)." in messages
    assert "Tu maná está completo. Dejas de meditar." in messages
    assert await world.redis.hget(key, "meditating") == "0"
    world.senders[1].connection.send.reset_mock()
    await MeditationEffect().apply(1, world.player, world.senders[1])
    world.senders[1].connection.send.assert_not_awaited()
    world.senders[2].connection.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_meditation_retries_failed_send_and_ignores_another_map(action_world):
    """Sólo recuerda envíos exitosos y no difunde el aura fuera del mapa actual."""
    world = action_world
    observer = world.senders[2]
    await observer.status_effects.sync_visibility(2, world.player, world.maps)
    await world.redis.hset(RedisKeys.player_user_stats(1), "meditating", "1")
    observer.connection.send.side_effect = ConnectionError("envío interrumpido")
    with pytest.raises(ConnectionError):
        await observer.status_effects.sync_visibility(2, world.player, world.maps)
    observer.connection.send.side_effect = None
    await observer.status_effects.sync_visibility(2, world.player, world.maps)
    assert observer.connection.send.await_args.args[0] == build_create_fx_response(1, 16, -1)
    world.maps.remove_player(2, 1)
    observer.connection.send.reset_mock()
    await observer.status_effects.sync_visibility(2, world.player, world.maps)
    observer.connection.send.assert_not_awaited()
    assert 1 not in observer.status_effects._meditation_fx
