"""Ediciones administrativas concurrentes antes de publicar los overlays en memoria."""

import asyncio
import json
from contextlib import suppress

import pytest

from src.services.classic_chat import admin_world

from .test_world_commands import select_tile


@pytest.mark.asyncio
async def test_two_gm_toggles_preserve_redis_and_memory_order(chat_world, monkeypatch):
    """Dos BLOQ simultáneos se cancelan incluso si el primer commit demora su publicación."""
    world = chat_world
    await world.deps.account_repo.set_gm_status("Invitado", True)
    await select_tile(world, 54, 54, user=1)
    await select_tile(world, 54, 54, user=3)
    committed, resume = asyncio.Event(), asyncio.Event()
    original = admin_world.audited

    async def delayed(ctx, *args: object, **kwargs: object):
        result = await original(ctx, *args, **kwargs)
        if ctx.user == 1:
            committed.set()
            await resume.wait()
        return result

    monkeypatch.setattr(admin_world, "audited", delayed)
    first = asyncio.create_task(world.run("/BLOQ", user=1))
    second = None
    try:
        await asyncio.wait_for(committed.wait(), 1)
        second = asyncio.create_task(world.run("/BLOQ", user=3))
        with suppress(TimeoutError):
            await asyncio.wait_for(asyncio.shield(second), 0.1)
    finally:
        resume.set()
        await first
        if second is not None:
            await second
    assert world.deps.map_manager.can_move_to(2, 54, 54)
    assert not world.deps.map_resources_service.is_blocked(2, 54, 54)
    assert json.loads(await world.redis.hget("world:map:tiles:2", "54,54"))["blocked"] is False


@pytest.mark.asyncio
async def test_regular_player_is_rejected_without_waiting_for_a_map_editor(chat_world):
    """Una edición en curso no bloquea el rechazo privado de un jugador sin permisos."""
    world = chat_world
    async with world.deps.map_manager.map_edit_lock:
        result = await asyncio.wait_for(world.run("/BLOQ", user=2), 0.5)
        assert "No tienes permisos" in result
    assert not await world.redis.exists("world:map:tiles:2")


@pytest.mark.asyncio
async def test_revoked_role_while_waiting_cannot_change_the_map(chat_world, monkeypatch):
    """Un permiso leído antes de esperar no habilita una escritura después de revocarlo."""
    world = chat_world
    await world.deps.account_repo.set_gm_status("Invitado", True)
    await select_tile(world, 54, 54, user=3)
    observed = asyncio.Event()
    original = world.deps.account_repo.get_account_by_user_id

    async def lookup(user):
        account = await original(user)
        if user == 3:
            observed.set()
        return account

    monkeypatch.setattr(world.deps.account_repo, "get_account_by_user_id", lookup)
    async with world.deps.map_manager.map_edit_lock:
        pending = asyncio.create_task(world.run("/BLOQ", user=3))
        await asyncio.wait_for(observed.wait(), 1)
        await world.deps.account_repo.set_gm_status("Invitado", False)
    assert "No tienes permisos" in await asyncio.wait_for(pending, 1)
    assert not await world.redis.exists("world:map:tiles:2")
