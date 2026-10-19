"""Canal negociado: identidad, revisiones, privacidad, reintentos y límites."""

import json
import struct
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.command_handlers.gm_command_handler import GMCommandHandler
from src.commands.gm_command import GMCommand
from src.economy.tax_transactions import tax_key
from src.economy.taxes import TAX_POLICY_KEY, utc_day
from src.effects.effect_pet_follow import PetFollowEffect
from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.models.clan import Clan, ClanMember
from src.models.item_catalog import ItemCatalog
from src.models.party import Party, PartyInvitation
from src.network.capabilities import Capability
from src.network.chat_channel import emit_chat
from src.repositories.account_repository import AccountRepository
from src.repositories.clan_repository import ClanRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.party_repository import PartyRepository
from src.repositories.player_repository import PlayerRepository
from src.services.action_cadence import ActionCadence
from src.services.clan_service import ClanService
from src.services.party_service import PartyService
from src.services.trade_service import TradeService
from src.services.world.trade_metadata import trade_metadata
from src.services.world.world_state import WorldStateService
from src.tasks.task_world_state import TaskWorldState
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


def connection(index):
    """Conexión sintética autenticada sin sockets ni información de acceso."""
    return SimpleNamespace(
        is_authenticated=True,
        capabilities=SimpleNamespace(enabled=Capability.WORLD_STATE | Capability.TRADE_STATE),
        state_epoch=f"{index:032x}",
        state_sequence=0,
        session_redis=None,
        session_user_id=None,
        state_pages={},
        state_topics=set(),
        state_tokens=8.0,
        state_budget_at=0.0,
        address=("127.0.0.1", index),
        send=AsyncMock(),
    )


@pytest_asyncio.fixture
async def world(redis_client):
    """Fachadas y repositorios reales sobre Redis simulado.

    Yields:
        Servicio, dependencias y tres emisores de personajes independientes.
    """
    maps = MapManager()
    players = PlayerRepository(redis_client)
    accounts = AccountRepository(redis_client)
    senders = {}
    for user in (1, 2, 3):
        sender = MessageSender(connection(user))
        senders[user] = sender
        await accounts.create_account(f"User{user}", "synthetic-hash", "test@example.invalid")
        await redis_client.hset(
            RedisKeys.player_user_stats(user),
            mapping={"gold": "1000", "min_hp": "100", "max_hp": "100", "level": "20"},
        )
        await players.set_position(user, 50 + user, 50, 1, 3)
        maps.add_player(1, user, sender, f"User{user}")
    party_repo, clan_repo = PartyRepository(redis_client), ClanRepository(redis_client)
    deps = SimpleNamespace(
        redis_client=redis_client,
        player_repo=players,
        account_repo=accounts,
        party_repo=party_repo,
        clan_repo=clan_repo,
        party_service=PartyService(
            party_repo, players, senders[1], map_manager=maps, account_repo=accounts
        ),
        clan_service=ClanService(clan_repo, players, senders[1], map_manager=maps),
        map_manager=maps,
        npc_repo=NPCRepository(redis_client),
        item_catalog=ItemCatalog(),
    )
    deps.npc_service = SimpleNamespace(map_manager=maps, npc_repository=deps.npc_repo)
    deps.trade_service = TradeService(
        players, InventoryRepository(redis_client), maps, monitor=False
    )
    state = WorldStateService(deps)
    with (
        patch("src.services.world.world_state.require_durable", new=AsyncMock()),
        patch("src.economy.tax_service.require_durable", new=AsyncMock()),
    ):
        yield state, deps, senders
    await state.close()
    await deps.trade_service.close()


def frames(sender):
    """Decodifica únicamente frames optativos, conservando su tamaño binario."""
    result = []
    for call in sender.connection.send.call_args_list:
        data = call.args[0]
        if data[0] != 248:
            continue
        packet, version, length = struct.unpack("<BBH", data[:4])
        assert packet == 248
        assert version == 1
        assert length == len(data) - 4
        assert len(data) <= 4096
        result.append(json.loads(data[4:].decode("ascii")))
    return result


async def request(state, sender, user, action, params=None, revision="", epoch=None, identity=None):
    """Construye una solicitud del mismo formato que el cliente."""
    value = {
        "id": identity or operation_id(),
        "epoch": sender.connection.state_epoch if epoch is None else epoch,
        "revision": revision,
        "action": action,
        "params": params or {},
    }
    raw = json.dumps(value, ensure_ascii=True).encode("ascii")
    packet = struct.pack("<BBH", 248, 1, len(raw)) + raw
    await TaskWorldState(packet, sender, state, {"user_id": user}).execute()
    return value


@pytest.mark.asyncio
async def test_tax_read_uses_authenticated_user_and_binary_bounds(world):
    """Una lectura no acepta identidades distintas y entrega saldos del servidor."""
    state, deps, senders = world
    await deps.redis_client.set(RedisKeys.bank_gold(1), "500")
    await request(state, senders[1], 1, "tax.read", epoch="")
    frame = frames(senders[1])[-1]
    assert frame["kind"] == "tax"
    assert frame["data"]["wallet"] == 1000
    assert frame["data"]["bank"] == 500
    assert frame["epoch"] == senders[1].connection.state_epoch
    count = len(frames(senders[1]))
    await request(state, senders[1], 1, "tax.read", {"user_id": 2})
    assert len(frames(senders[1])) == count


@pytest.mark.asyncio
async def test_non_member_cannot_read_another_clan_roster(world):
    """El clan consultado se deriva de la pertenencia y no de un ID enviado."""
    state, deps, senders = world
    clan = Clan(clan_id=1, name="Private", leader_id=1, leader_username="User1")
    await deps.clan_repo.save_clan(clan)
    await request(state, senders[3], 3, "clan.read", {"page": 0})
    snapshot = frames(senders[3])[-1]["data"]
    assert snapshot["clan_id"] == 0
    assert snapshot["members"] == []
    assert "User1" not in json.dumps(snapshot)


@pytest.mark.asyncio
async def test_old_connection_epoch_cannot_dispatch_a_mutation(world):
    """Una cola de la conexión anterior no se ejecuta después de reconectar."""
    state, deps, senders = world
    await request(state, senders[1], 1, "party.create", epoch="f" * 32)
    assert not frames(senders[1])[-1]["data"]["applied"]
    assert await deps.party_repo.get_user_party(1) is None


@pytest.mark.asyncio
async def test_stale_revision_refreshes_without_mutating(world):
    """Confirmar una revisión desconocida no crea ni cambia el grupo."""
    state, deps, senders = world
    await request(state, senders[1], 1, "party.create", revision="stale")
    result = next(f for f in frames(senders[1]) if f["kind"] == "result")
    assert not result["data"]["applied"]
    assert await deps.party_repo.get_user_party(1) is None


@pytest.mark.asyncio
async def test_identified_social_action_replays_without_reapplying(world):
    """Repetir rechazar una invitación devuelve el primer resultado confirmado."""
    state, deps, senders = world
    party = Party(1, 1, "User1")
    party.members[1].level = 20
    await deps.party_repo.save_party(party)
    await deps.party_repo.save_invitation(PartyInvitation(1, 1, "User1", 3, "User3"))
    await request(state, senders[3], 3, "party.read")
    revision = frames(senders[3])[-1]["revision"]
    identity = operation_id()
    for _ in range(2):
        await request(
            state, senders[3], 3, "party.reject", {"party_id": 1}, revision, identity=identity
        )
    results = [f["data"] for f in frames(senders[3]) if f["kind"] == "result"]
    assert len(results) == 2
    assert results[0] == results[1]
    assert results[0]["applied"]
    assert await deps.party_repo.get_invitation(3, 1) is None


@pytest.mark.asyncio
async def test_unnegotiated_client_receives_no_world_frames(world):
    """Los clientes legacy conservan su stream sin extensiones nuevas."""
    state, _deps, senders = world
    senders[1].connection.capabilities.enabled = 0
    await state.initial(1, senders[1])
    await request(state, senders[1], 1, "tax.read")
    assert frames(senders[1]) == []


@pytest.mark.asyncio
async def test_party_disconnect_changes_revision_but_hp_does_not_block_management(world):
    """Una desconexión invalida menús; la vida cambia sin impedir administrar en combate."""
    state, deps, senders = world
    party = Party(1, 1, "User1")
    party.members[1].level = 20
    assert party.add_member(2, "User2", 20)
    await deps.party_repo.save_party(party)
    await state.publish(1, "party")
    original = frames(senders[1])[-1]["revision"]
    await deps.redis_client.hset(RedisKeys.player_user_stats(2), "min_hp", "50")
    await state.publish(1, "party")
    assert frames(senders[1])[-1]["revision"] == original
    deps.map_manager.remove_player(1, 2)
    await state.publish(1, "party")
    assert frames(senders[1])[-1]["revision"] != original
    assert not next(m for m in frames(senders[1])[-1]["data"]["members"] if m["id"] == 2)["online"]


@pytest.mark.asyncio
async def test_gm_warp_uses_target_connection_and_native_transition(world):
    """El GM mueve al objetivo con su emisor, sin cambiar el actor de la sesión."""
    _state, deps, senders = world
    await deps.account_repo.set_gm_status("User1", True)
    deps.map_manager._map_sizes[2] = (100, 100)
    maps = SimpleNamespace(
        map_manager=deps.map_manager,
        transition_to_map=AsyncMock(),
        teleport_in_same_map=AsyncMock(),
    )
    handler = GMCommandHandler(
        deps.player_repo, deps.account_repo, maps, senders[1], ActionCadence()
    )
    result = await handler.handle(GMCommand(1, 1, "user2", 2, 20, 20))
    assert result.success
    maps.transition_to_map.assert_awaited_once()
    arguments = maps.transition_to_map.call_args.kwargs
    assert arguments["user_id"] == 2
    assert arguments["message_sender"] is senders[2]
    assert deps.map_manager.can_move_to(2, 20, 20)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["ordinary", "offline", "occupied", "unknown_map", "out_of_bounds", "moving"]
)
async def test_gm_warp_rejects_invalid_target_or_destination_without_changes(world, case):
    """Permisos, cuenta, casilla y movimiento se validan antes de la transición."""
    _state, deps, senders = world
    if case != "ordinary":
        await deps.account_repo.set_gm_status("User1", True)
    deps.map_manager._map_sizes[2] = (100, 100)
    maps = SimpleNamespace(
        map_manager=deps.map_manager,
        transition_to_map=AsyncMock(),
        teleport_in_same_map=AsyncMock(),
    )
    cadence = ActionCadence()
    if case == "offline":
        deps.map_manager.remove_player(1, 2)
    elif case == "occupied":
        deps.map_manager.block_tile(2, 20, 20)
    elif case == "moving":
        assert cadence.claim(2, "walk")
    handler = GMCommandHandler(deps.player_repo, deps.account_repo, maps, senders[1], cadence)
    before = await deps.player_repo.get_position(2)
    result = await handler.handle(
        GMCommand(
            1,
            1,
            "User2",
            999 if case == "unknown_map" else 2,
            0 if case == "out_of_bounds" else 20,
            20,
        )
    )
    assert not result.success
    maps.transition_to_map.assert_not_awaited()
    assert await deps.player_repo.get_position(2) == before


@pytest.mark.asyncio
async def test_private_party_channel_checks_current_membership(world, caplog):
    """El canal no depende del color y los expulsados dejan de recibir texto privado."""
    _state, deps, senders = world
    party = Party(1, 1, "User1")
    party.members[1].level = 20
    party.members[1].level = 20
    assert party.add_member(2, "User2", 20)
    await deps.party_repo.save_party(party)
    canary = "PRIVATE_PARTY_SYNTHETIC_771"
    await deps.party_service.send_party_message(1, canary)
    for user in (1, 2):
        chat = [frame["data"] for frame in frames(senders[user]) if frame["kind"] == "chat"]
        assert len(chat) == 1
        assert chat[0]["channel"] == "party"
        assert chat[0]["sender_id"] == 1
        assert chat[0]["text"] == canary
    assert frames(senders[3]) == []
    await deps.party_service.kick_member(1, "User2")
    count = len(frames(senders[2]))
    await deps.party_service.send_party_message(1, canary)
    assert len(frames(senders[2])) == count
    assert canary not in caplog.text


@pytest.mark.asyncio
async def test_unicode_chat_is_bounded_and_preserves_every_character(world):
    """Las cadenas escapadas de peor tamaño no exceden el límite del frame."""
    _state, _deps, senders = world
    text = "ñ" * 1000
    await emit_chat(
        senders[1],
        "whisper",
        2,
        "á" * 20,
        text,
        context="ó" * 32,
        recipient=1,
        recipient_name="ú" * 20,
    )
    data = [frame["data"] for frame in frames(senders[1])]
    assert len(data) == 3
    assert "".join(item["text"] for item in data) == text
    assert all(item["channel"] == "whisper" and item["recipient"] == 1 for item in data)


async def own_pet(deps):
    """Instancia real persistida y publicada en el índice del mundo."""
    pet = await deps.npc_repo.create_npc_instance(
        1,
        10001,
        1,
        60,
        50,
        3,
        "Pet",
        "",
        1,
        0,
        100,
        100,
        1,
        False,
        True,
        0,
        0,
        0,
        0,
        summoned_by_user_id=1,
        summoned_until=time.time() + 600,
    )
    deps.map_manager.add_npc(1, pet)
    return pet


@pytest.mark.asyncio
async def test_pet_orders_reject_forged_owner_and_wait_resumes_follow(world):
    """Propiedad persistida, consulta privada y la IA obedecen la misma orden."""
    state, deps, _senders = world
    pet = await own_pet(deps)
    assert state.pets.snapshot(2)["pets"] == []
    rejected = await state.pets.command(2, pet.instance_id, "wait", operation_id())
    assert not rejected["applied"]
    assert pet.pet_order == "follow"
    accepted = await state.pets.command(1, pet.instance_id, "wait", operation_id())
    assert accepted["applied"]
    assert (await deps.npc_repo.get_npc(pet.instance_id)).pet_order == "wait"
    effect = PetFollowEffect(deps.npc_service, interval_seconds=0)
    with patch.object(effect, "_move_pet_towards_owner", new=AsyncMock()) as move:
        await effect.apply(1, deps.player_repo, None)
        move.assert_not_awaited()
        await state.pets.command(1, pet.instance_id, "follow", operation_id())
        await effect.apply(1, deps.player_repo, None)
        move.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("field", "value"), [("hp", "0"), ("summoned_until", "1"), ("summoned_by_user_id", "2")]
)
async def test_dead_expired_or_reassigned_pet_cannot_receive_order(world, field, value):
    """Una UI vieja no conserva autoridad sobre una instancia que dejó de estar vigente."""
    state, deps, _senders = world
    pet = await own_pet(deps)
    await deps.redis_client.hset(RedisKeys.npc_instance(pet.instance_id), field, value)
    result = await state.pets.command(1, pet.instance_id, "wait", operation_id())
    assert not result["applied"]
    assert pet.pet_order == "follow"


@pytest.mark.asyncio
async def test_weather_idempotence_map_scope_interiors_and_permissions(world):
    """No hay toggle; cambiar de mapa toma su estado, incluidos defaults interiores."""
    state, deps, senders = world
    params = {"map": 1, "raining": True, "intensity": 80}
    assert not (await state.weather.set(2, params, operation_id()))["applied"]
    await deps.account_repo.set_gm_status("User1", True)
    for _ in range(2):
        assert (await state.weather.set(1, params, operation_id()))["applied"]
    assert await deps.redis_client.hget("world:weather:1", "revision") == "1"
    await state.publish(2, "weather")
    assert frames(senders[2])[-1]["data"]["raining"]
    interior = next(
        int(key[4:]) for key, row in state.weather.maps.items() if row.get("type") == "dungeon"
    )
    await deps.player_repo.set_position(2, 50, 50, interior, 3)
    await state.publish(2, "weather")
    assert not frames(senders[2])[-1]["data"]["raining"]
    assert not frames(senders[2])[-1]["data"]["outdoor"]
    assert frames(senders[3]) == []
    assert not (await state.weather.set(1, {**params, "map": interior}, operation_id()))["applied"]


@pytest.mark.asyncio
async def test_legacy_tax_notices_update_both_balances_once_per_receipt(world):
    """El cobro offline informa sin enviar extensiones a clientes anteriores."""
    state, deps, senders = world
    redis = deps.redis_client.redis
    day = utc_day()
    await redis.hset(
        TAX_POLICY_KEY,
        mapping={"version": "1", "enabled": "1", "rate_bps": "100", "activation_day": str(day - 1)},
    )
    await redis.hset(
        tax_key(1),
        mapping={"version": "1", "last_day": str(day - 1), "remainder": "0", "total_paid": "0"},
    )
    await redis.set(RedisKeys.bank_gold(1), "2000")
    senders[1].connection.capabilities.enabled = 0
    await state.publish_legacy_tax(1, senders[1])
    calls = list(senders[1].connection.send.call_args_list)
    await state.publish_legacy_tax(1, senders[1])
    assert senders[1].connection.send.call_args_list == calls
    assert frames(senders[1]) == []
    assert int(await redis.hget(RedisKeys.player_user_stats(1), "gold")) == 990
    assert int(await redis.get(RedisKeys.bank_gold(1))) == 1980
    assert len(calls) == 3


@pytest.mark.asyncio
async def test_clan_private_chat_and_permissions_change_after_transfer(world, caplog):
    """Una transferencia invalida la revisión y no filtra el canal a terceros."""
    state, deps, senders = world
    clan = Clan(clan_id=1, name="Private", leader_id=1, leader_username="User1")
    assert clan.add_member(ClanMember(2, "User2", 20))
    await deps.clan_repo.save_clan(clan)
    await deps.clan_service.send_clan_message(1, "CLAN_PRIVATE_CANARY")
    for user in (1, 2):
        chats = [f["data"] for f in frames(senders[user]) if f["kind"] == "chat"]
        assert chats[-1]["channel"] == "clan"
    assert frames(senders[3]) == []
    await state.publish(1, "clan")
    before = frames(senders[1])[-1]
    await request(state, senders[1], 1, "clan.transfer", {"username": "User2"}, before["revision"])
    after = frames(senders[1])[-1]
    assert after["data"]["leader"] == 2
    assert "transfer" not in after["data"]["permissions"]
    assert after["revision"] != before["revision"]
    await request(state, senders[1], 1, "clan.kick", {"username": "User2"}, before["revision"])
    assert (await deps.clan_repo.get_user_clan(2)).leader_id == 2
    assert "CLAN_PRIVATE_CANARY" not in caplog.text


@pytest.mark.asyncio
async def test_trade_metadata_is_authorized_paged_and_tied_to_exact_offer(world):
    """Los dos participantes ven nombres actuales; terceros y revisiones viejas se rechazan."""
    state, deps, senders = world
    inventory = deps.trade_service.inventory_repo
    for item in (15, 38, 37, 1, 4):
        await inventory.add_item(1, item, 1)
    accepted, _message = await deps.trade_service.request_trade(1, "User2")
    assert accepted
    session = deps.trade_service.get_session(1)
    accepted, _message = await deps.trade_service.apply_action(
        2, session.session_id, session.revision, 0, 0, 0
    )
    assert accepted
    session = deps.trade_service.get_session(1)
    for slot in range(1, 6):
        accepted, _message = await deps.trade_service.update_offer(
            1, slot, 1, revision=session.revision
        )
        assert accepted
    first = trade_metadata(deps, 2, session.session_id, session.revision, 0)
    second = trade_metadata(deps, 2, session.session_id, session.revision, 1)
    assert first["pages"] == 2
    assert {item["id"] for item in first["items"] + second["items"]} == {15, 38, 37, 1, 4}
    assert all(item["known"] and item["name"] for item in first["items"] + second["items"])
    with pytest.raises(ValueError, match="cambió"):
        trade_metadata(deps, 3, session.session_id, session.revision, 0)
    with pytest.raises(ValueError, match="cambió"):
        trade_metadata(deps, 2, session.session_id, session.revision - 1, 0)
    old_revision = session.revision
    senders[1].connection.send.reset_mock()

    async def edit_after_first_page(_frame):
        session.revision = old_revision + 1
        session.initiator_offer.items.clear()

    senders[1].connection.send.side_effect = edit_after_first_page
    await state.publish_trade(1)
    pages = [f["data"] for f in frames(senders[1]) if f["kind"] == "trade"]
    assert len(pages) == 2
    assert all(page["trade_revision"] == old_revision for page in pages)
    assert sum(len(page["items"]) for page in pages) == 5


@pytest.mark.asyncio
async def test_pet_release_uses_own_instance_and_cannot_touch_reused_character_index(world):
    """Liberar confirma la instancia; repetir no afecta otra mascota con el mismo char_index."""
    state, deps, _senders = world
    pet = await own_pet(deps)

    async def remove(value):
        await deps.npc_repo.remove_npc(value.instance_id)
        deps.map_manager.remove_npc(value.map_id, value.instance_id)

    deps.npc_service.remove_npc = AsyncMock(side_effect=remove)
    identity = operation_id()
    denied = await state.pets.command(2, pet.instance_id, "release", operation_id())
    assert not denied["applied"]
    first = await state.pets.command(1, pet.instance_id, "release", identity)
    other = await own_pet(deps)
    again = await state.pets.command(1, pet.instance_id, "release", identity)
    assert first == again
    assert first["applied"]
    assert await deps.npc_repo.get_npc(pet.instance_id) is None
    assert await deps.npc_repo.get_npc(other.instance_id) is not None
    deps.npc_service.remove_npc.assert_awaited_once()


@pytest.mark.asyncio
async def test_accept_party_uses_connected_account_name_for_management(world):
    """Aceptar no inventa PlayerN cuando los atributos no incluyen username."""
    state, deps, senders = world
    await deps.redis_client.hset("player:2:stats", mapping={"charisma": "20"})
    party = Party(1, 1, "User1")
    party.members[1].level = 20
    await deps.party_repo.save_party(party)
    await deps.party_repo.save_invitation(PartyInvitation(1, 1, "User1", 2, "User2"))
    await request(state, senders[2], 2, "party.read")
    revision = frames(senders[2])[-1]["revision"]
    await request(state, senders[2], 2, "party.accept", {"party_id": 1}, revision)
    party = await deps.party_repo.get_user_party(1)
    assert party.members[2].username == "User2"
    await deps.party_service.transfer_leadership(1, "User2")
    assert (await deps.party_repo.get_user_party(2)).leader_id == 2


@pytest.mark.asyncio
async def test_old_leader_invitation_is_invalidated_on_accept(world):
    """Una invitación no conserva autoridad tras transferir el grupo."""
    _state, deps, _senders = world
    party = Party(1, 1, "User1")
    party.members[1].level = 20
    assert party.add_member(3, "User3", 20)
    await deps.party_repo.save_party(party)
    await deps.party_repo.save_invitation(PartyInvitation(1, 1, "User1", 2, "User2"))
    await deps.party_service.transfer_leadership(1, "User3")
    applied, message, _party = await deps.party_service.can_accept_invitation(2, 1)
    assert not applied
    assert "líder" in message
    assert await deps.party_repo.get_invitation(2, 1) is None
