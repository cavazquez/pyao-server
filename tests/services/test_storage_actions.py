"""Bóveda y ficha de clan: concurrencia, permisos, recibos y AOF real optativo."""

import asyncio
import json
import os
from contextlib import ExitStack
from hashlib import sha256
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.config.game_config import RedisConfig
from src.models.clan import Clan, ClanMember, ClanRank
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.bank_repository import BankRepository
from src.repositories.clan_repository import ClanRepository
from src.services.bank_item_transfer import transfer_bank_item
from src.services.world.bank import BankState
from src.services.world.clan_profile import update_profile
from src.utils.gold_atomic import operation_id
from src.utils.slot_plan import SlotPlan


@pytest.fixture(scope="module")
def storage_sandbox():
    """Aísla la campaña real del Redis del operador.

    Yields:
        Contenedor nuevo o None en la suite rápida.
    """
    if os.environ.get("PYAO_RUN_STORAGE_REDIS") != "1":
        yield None
        return
    with RedisSandbox() as sandbox:
        yield sandbox


@pytest_asyncio.fixture
async def storage(redis_client, storage_sandbox):
    """Usa los mismos planes y repositorios en Redis fake y real.

    Yields:
        Dos miembros, dos objetos bancarios y un banquero próximo.
    """
    if storage_sandbox:
        await redis_client.redis.aclose()
        redis_client._redis = None
        await redis_client.connect(
            RedisConfig(
                host="127.0.0.1",
                port=storage_sandbox.port,
                password_file=storage_sandbox.password_file,
            ),
            seed_defaults=False,
        )
        await redis_client.redis.flushdb()
    redis = redis_client.redis
    sender = SimpleNamespace(connection=SimpleNamespace(bank_npc="banker"))
    deps = SimpleNamespace(
        redis_client=redis_client,
        bank_repo=BankRepository(redis_client),
        clan_repo=ClanRepository(redis_client),
        map_manager=SimpleNamespace(
            get_player_message_sender=lambda user: sender if user == 1 else None
        ),
    )
    clan = Clan(7, "Prueba", description="Códice inicial", leader_id=1, leader_username="Líder")
    clan.members[2] = ClanMember(2, "Miembro", level=20, rank=ClanRank.MEMBER)
    await deps.clan_repo.save_clan(clan)
    await redis.hset("player:1:position", mapping={"map": "1", "x": "50", "y": "50"})
    await redis.hset("player:1:user_stats", mapping={"min_hp": "100"})
    await redis.hset("bank:1:vault", mapping={"slot_1": "1:5", "slot_2": "2:3"})
    await redis.hset(
        "npc:instance:banker",
        mapping={"map_id": "1", "x": "51", "y": "50", "hp": "100", "is_banker": "True"},
    )
    with ExitStack() as stack:
        if not storage_sandbox:
            for module in ("bank", "clan_profile"):
                for function in ("ensure_aof", "require_durable"):
                    stack.enter_context(
                        patch(f"src.services.world.{module}.{function}", AsyncMock())
                    )
            stack.enter_context(
                patch("src.services.bank_item_transfer.require_durable", AsyncMock())
            )
        yield SimpleNamespace(
            deps=deps,
            sender=sender,
            bank=BankState(deps),
            client=redis_client,
            redis=redis,
            sandbox=storage_sandbox,
        )
    if storage_sandbox:
        await redis_client.disconnect()


async def move_request(game, source=1, destination=2):
    """Captura una revisión previa sin fabricar el contenido del banco.

    Returns:
        Petición coordinada igual a la enviada por Godot.
    """
    return {
        "id": operation_id(),
        "revision": sha256(
            json.dumps(await game.bank.snapshot(1), sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:32],
        "params": {"source": source, "destination": destination, "banker": "banker"},
    }


def profile_request(**changes: str | int):
    """Prepara una edición de la ficha del clan.

    Returns:
        Petición con versión e identidad explícitas.
    """
    return {
        "id": operation_id(),
        "params": {
            "clan": 7,
            "version": 0,
            "description": "Código nuevo",
            "news": "Noticias",
            "website": "https://example.invalid/clan",
            **changes,
        },
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("destination", [2, 40])
async def test_bank_swap_empty_or_occupied_is_idempotent(storage, destination):
    """Bank swap empty or occupied is idempotent."""
    request = await move_request(storage, destination=destination)
    before = await storage.redis.hgetall("bank:1:vault")
    result = await storage.bank.move(1, storage.sender, request)
    assert result["applied"]
    after = await storage.redis.hgetall("bank:1:vault")
    assert after[f"slot_{destination}"] == before["slot_1"]
    assert after["slot_1"] == before.get(f"slot_{destination}", "")
    assert await storage.bank.move(1, storage.sender, request) == result
    assert await storage.redis.hgetall("bank:1:vault") == after


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "destination"), [(0, 1), (41, 2), (1, 0), (1, 41), (1, 1), (40, 2)]
)
async def test_bank_invalid_slots_preserve_every_object(storage, source, destination):
    """Bank invalid slots preserve every object."""
    before = await storage.redis.hgetall("bank:1:vault")
    result = await storage.bank.move(
        1, storage.sender, await move_request(storage, source, destination)
    )
    assert not result["applied"]
    assert await storage.redis.hgetall("bank:1:vault") == before


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["closed", "far", "dead", "npc", "session"])
async def test_bank_rechecks_access_at_commit(storage, change):
    """Bank rechecks access at commit."""
    request = await move_request(storage)
    before = await storage.redis.hgetall("bank:1:vault")
    if change == "closed":
        storage.sender.connection.bank_npc = ""
    elif change == "far":
        await storage.redis.hset("player:1:position", "x", "90")
    elif change == "dead":
        await storage.redis.hset("player:1:user_stats", "min_hp", "0")
    elif change == "npc":
        await storage.redis.hset("npc:instance:banker", "is_banker", "False")
    else:
        storage.deps.map_manager.get_player_message_sender = lambda _user: None
    assert not (await storage.bank.move(1, storage.sender, request))["applied"]
    assert await storage.redis.hgetall("bank:1:vault") == before


@pytest.mark.asyncio
async def test_bank_concurrent_swaps_do_not_swap_back(storage):
    """Bank concurrent swaps do not swap back."""
    first, second = await move_request(storage), await move_request(storage)
    results = await asyncio.gather(
        *(storage.bank.move(1, storage.sender, request) for request in (first, second))
    )
    assert sum(result["applied"] for result in results) == 1
    assert await storage.redis.hget("bank:1:vault", "slot_1") == "2:3"


@pytest.mark.asyncio
async def test_city_banker_without_hp_is_available_but_dead_attackable_npc_is_not(storage):
    """Los banqueros permanentes del catálogo usan hp_max=0 e invulnerabilidad."""
    await storage.redis.hset(
        "npc:instance:banker",
        mapping={"hp": "0", "max_hp": "0", "is_attackable": "False", "is_hostile": "False"},
    )
    assert (await storage.bank.move(1, storage.sender, await move_request(storage)))["applied"]
    await storage.redis.hset(
        "npc:instance:banker", mapping={"max_hp": "100", "is_attackable": "True"}
    )
    assert not (await storage.bank.move(1, storage.sender, await move_request(storage)))["applied"]


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["deposit", "withdraw"])
async def test_bank_transfer_invalidates_old_bank_revision(storage, direction):
    """Ni un depósito ni una extracción permiten reutilizar la revisión previa."""
    request = await move_request(storage)
    await storage.redis.hset("player:1:inventory", "slot_1", "1:4")
    result = await transfer_bank_item(storage.redis, 1, 1, 4, direction, operation_id())
    assert result["applied"]
    assert not (await storage.bank.move(1, storage.sender, request))["applied"]
    expected = "1:9" if direction == "deposit" else "1:1"
    assert await storage.redis.hget("bank:1:vault", "slot_1") == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("direction", ["deposit", "withdraw"])
async def test_bank_move_competes_with_transfer_without_losing_or_duplicating(storage, direction):
    """WATCH reintenta el estado vigente cuando depósito/extracción y drag compiten."""
    await storage.redis.hset("player:1:inventory", "slot_1", "1:4")
    request = await move_request(storage)
    transfer_id = operation_id()
    _, transfer = await asyncio.gather(
        storage.bank.move(1, storage.sender, request),
        transfer_bank_item(storage.redis, 1, 1, 1, direction, transfer_id),
    )
    keys = ("bank:1:vault", "player:1:inventory")
    after = [await storage.redis.hgetall(key) for key in keys]
    amounts = {}
    for raw in after:
        for item in SlotPlan(raw, 40, 32767).slots.values():
            amounts[item.item_id] = amounts.get(item.item_id, 0) + item.quantity
    assert amounts == {1: 9, 2: 3}
    assert await transfer_bank_item(storage.redis, 1, 1, 1, direction, transfer_id) == transfer
    await storage.bank.move(1, storage.sender, request)
    assert [await storage.redis.hgetall(key) for key in keys] == after


@pytest.mark.asyncio
async def test_bank_lost_ack_is_recovered_even_after_closing(storage):
    """Bank lost ack is recovered even after closing."""
    request = await move_request(storage)
    with (
        patch(
            "src.services.world.bank.require_durable",
            AsyncMock(side_effect=RuntimeError("ACK lost")),
        ),
        pytest.raises(RuntimeError, match="ACK lost"),
    ):
        await storage.bank.move(1, storage.sender, request)
    storage.sender.connection.bank_npc = ""
    assert (await storage.bank.move(1, storage.sender, request))["applied"]
    assert await storage.redis.hget("bank:1:vault", "slot_1") == "2:3"


@pytest.mark.asyncio
async def test_clan_profile_permissions_and_replay(storage):
    """Clan profile permissions and replay."""
    request = profile_request()
    assert not (await update_profile(storage.deps, 2, request))["applied"]
    request["id"] = operation_id()
    result = await update_profile(storage.deps, 1, request)
    assert result["applied"]
    assert result["version"] == 1
    clan = await storage.deps.clan_repo.get_clan(7)
    assert (clan.description, clan.news, clan.website) == (
        "Código nuevo",
        "Noticias",
        "https://example.invalid/clan",
    )
    await storage.deps.clan_repo.save_clan(Clan(7, "Prueba", leader_id=1, leader_username="Líder"))
    assert (await storage.deps.clan_repo.get_clan(7)).description == "Código nuevo"
    assert await update_profile(storage.deps, 1, request) == result


@pytest.mark.asyncio
async def test_clan_profile_concurrency_and_leader_change(storage):
    """Clan profile concurrency and leader change."""
    results = await asyncio.gather(
        *(
            update_profile(storage.deps, 1, profile_request(news=value))
            for value in ("Primera", "Segunda")
        )
    )
    assert sum(result["applied"] for result in results) == 1
    assert any(result.get("conflict") for result in results)
    metadata = json.loads(await storage.redis.get("clan:7"))
    metadata["leader_id"] = 2
    await storage.redis.set("clan:7", json.dumps(metadata))
    # A stale rank=4 entry alone cannot authorize the ex-leader.
    assert not (await update_profile(storage.deps, 1, profile_request(version=1)))["applied"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [
        {"description": "x" * 201},
        {"news": "\x00"},
        {"website": "javascript:alert(1)"},
        {"website": "https://user:secret@example.invalid"},
        {"website": "https://example.invalid/a b"},
    ],
)
async def test_clan_profile_rejects_invalid_fields_without_writes(storage, changes):
    """Clan profile rejects invalid fields without writes."""
    with pytest.raises(ValueError, match=r"campo|control|sitio|dirección"):
        await update_profile(storage.deps, 1, profile_request(**changes))
    assert await storage.redis.hgetall("clan:7:profile") == {}


@pytest.mark.asyncio
async def test_aof_restart_keeps_bank_and_public_profile(storage):
    """Aof restart keeps bank and public profile."""
    if storage.sandbox is None:
        pytest.skip("Requiere PYAO_RUN_STORAGE_REDIS=1")
    request = await move_request(storage)
    await storage.bank.move(1, storage.sender, request)
    await update_profile(storage.deps, 1, profile_request())
    await storage.client.disconnect()
    await asyncio.to_thread(docker, "kill", "--signal", "KILL", storage.sandbox.name)
    await asyncio.to_thread(docker, "start", storage.sandbox.name)
    with storage.sandbox.client() as client:
        assert client.ping()
    await storage.client.connect(
        RedisConfig(
            host="127.0.0.1", port=storage.sandbox.port, password_file=storage.sandbox.password_file
        ),
        seed_defaults=False,
    )
    assert await storage.client.hget("bank:1:vault", "slot_1") == "2:3"
    assert (await storage.deps.clan_repo.get_clan(7)).profile_revision == 1
    assert (await storage.bank.move(1, storage.sender, request))["applied"]


@pytest.mark.asyncio
async def test_aof_restart_and_ack_loss_do_not_repeat_physical_combat(storage, mechanics_world):
    """El golpe durable sobrevive SIGKILL y su recibo impide repetir sus efectos."""
    if storage.sandbox is None:
        pytest.skip("Requiere PYAO_RUN_STORAGE_REDIS=1")
    from src.services.combat.physical_plan import PhysicalPlan, PhysicalRequest, commit_physical  # ruff: ignore[import-outside-top-level]
    from src.utils.durability import ensure_aof, require_durable  # ruff: ignore[import-outside-top-level]

    world = mechanics_world
    identity = operation_id()

    def plan():
        return PhysicalPlan(
            PhysicalRequest(1, 0, world.npc.instance_id, False), world.catalog, 30, 20
        )

    with (
        patch("src.services.combat.physical_plan.ensure_aof", ensure_aof),
        patch("src.services.combat.physical_plan.require_durable", require_durable),
    ):
        first = await commit_physical(storage.client.redis, plan(), identity)
        assert first["applied"]
        keys = [f"npc:instance:{world.npc.instance_id}", "player:1:user_stats", "player:1:skills"]
        after = [await storage.client.hgetall(key) for key in keys]
        await storage.client.disconnect()
        await asyncio.to_thread(docker, "kill", "--signal", "KILL", storage.sandbox.name)
        await asyncio.to_thread(docker, "start", storage.sandbox.name)
        with storage.sandbox.client() as client:
            assert client.ping()
        await storage.client.connect(
            RedisConfig(
                host="127.0.0.1",
                port=storage.sandbox.port,
                password_file=storage.sandbox.password_file,
            ),
            seed_defaults=False,
        )
        assert await commit_physical(storage.client.redis, plan(), identity) == first
        assert [await storage.client.hgetall(key) for key in keys] == after
