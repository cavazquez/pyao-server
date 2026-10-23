"""Solicitudes acotadas por grupo, sin explorar claves ajenas ni perder concurrencia."""

import asyncio
import json
import time
from unittest.mock import AsyncMock

import pytest

from src.models.party import Party
from src.services.expansion.party_finder import MAX_REQUESTS, REQUEST_SECONDS
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from tests.services.test_world_state import world

__all__ = ["world"]


async def advertise(state, deps):
    """Crea un anuncio real sobre el que operan las solicitudes de cada prueba."""
    party = Party(1, 1, "User1")
    party.update_member_level(1, 20)
    await deps.party_repo.save_party(party)
    result = await state.expansion.finder.command(
        1,
        "publish",
        {"min_level": 1, "max_level": 100, "activity": "caza", "text": "Caza", "seconds": 600},
        operation_id(),
    )
    assert result["applied"]


@pytest.mark.asyncio
async def test_parallel_requests_survive_without_scanning_unrelated_keys(world, monkeypatch):
    """WATCH protege el documento compartido y la lectura no depende del tamaño global."""
    state, deps, _ = world
    await advertise(state, deps)
    redis = deps.redis_client.redis
    await redis.mset({f"unrelated:item:{i}": "fixture" for i in range(1000)})

    def forbidden_scan(*_args: object, **_kwargs: object) -> None:
        message = "El buscador no debe ejecutar SCAN global"
        raise AssertionError(message)

    monkeypatch.setattr(redis, "scan_iter", forbidden_scan)
    identities = [operation_id(), operation_id()]
    results = await asyncio.gather(
        *(
            state.expansion.finder.command(user, "request", {"party": 1}, identity)
            for user, identity in zip((2, 3), identities, strict=True)
        )
    )
    assert all(result["applied"] for result in results)
    snapshot = await state.expansion.finder.snapshot(1, {})
    assert {row["id"] for row in snapshot["requests"]} == {2, 3}
    assert not (await state.expansion.finder.snapshot(2, {}))["requests"]
    assert await redis.mget("user:2:party", "user:3:party") == [None, None]
    assert 0 < await redis.ttl("finder:requests:1") <= REQUEST_SECONDS
    # Repetir la misma identidad devuelve el recibo, sin crear otra solicitud.
    replay = await state.expansion.finder.command(2, "request", {"party": 1}, identities[0])
    assert replay == results[0]
    assert len(json.loads(await redis.get("finder:requests:1"))) == 2


@pytest.mark.asyncio
async def test_request_limit_expiration_and_close(world):
    """Renovar otro solicitante no revive los vencidos y cerrar borra el documento."""
    state, deps, _ = world
    await advertise(state, deps)
    redis = deps.redis_client.redis
    rows = {
        str(user): {"id": user, "name": f"User{user}", "level": 20, "expires": time.time() + 60}
        for user in range(3, MAX_REQUESTS + 3)
    }
    await redis.set("finder:requests:1", json.dumps(rows), ex=REQUEST_SECONDS)
    result = await state.expansion.finder.command(2, "request", {"party": 1}, operation_id())
    assert not result["applied"]
    assert len(json.loads(await redis.get("finder:requests:1"))) == MAX_REQUESTS
    rows["3"]["expires"] = time.time() - 1
    await redis.set("finder:requests:1", json.dumps(rows), ex=REQUEST_SECONDS)
    assert len((await state.expansion.finder.snapshot(1, {}))["requests"]) == MAX_REQUESTS - 1
    result = await state.expansion.finder.command(2, "request", {"party": 1}, operation_id())
    assert result["applied"]
    saved = json.loads(await redis.get("finder:requests:1"))
    assert "3" not in saved
    assert "2" in saved
    assert len(saved) == MAX_REQUESTS
    assert not (await state.expansion.finder.command(3, "close", {}, operation_id()))["applied"]
    assert (await state.expansion.finder.command(1, "close", {}, operation_id()))["applied"]
    assert await redis.get("finder:requests:1") is None


@pytest.mark.asyncio
async def test_invitation_requires_live_request_and_normal_consent(world, monkeypatch):
    """Invitar mantiene PartyService como autoridad y rechaza solicitudes vencidas."""
    state, deps, _ = world
    await advertise(state, deps)
    redis = deps.redis_client.redis
    await state.expansion.finder.command(2, "request", {"party": 1}, operation_id())
    result = await state.expansion.finder.command(1, "invite", {"user": 2}, operation_id())
    assert result["applied"], result
    assert await redis.get("user:2:party") is None
    assert await deps.party_repo.get_invitation(2, 1) is not None
    rows = json.loads(await redis.get("finder:requests:1"))
    rows["2"]["expires"] = time.time() - 1
    await redis.set("finder:requests:1", json.dumps(rows), ex=REQUEST_SECONDS)
    invite = AsyncMock()
    monkeypatch.setattr(deps.party_service, "invite_to_party", invite)
    result = await state.expansion.finder.command(1, "invite", {"user": 2}, operation_id())
    assert not result["applied"]
    invite.assert_not_awaited()
    assert await redis.hget(RedisKeys.player_user_stats(2), "min_hp") == "100"
