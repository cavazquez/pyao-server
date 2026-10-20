"""Recompensas reales sobre Redis: un commit por muerte, no mocks de oro o experiencia."""

import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest_asyncio

from src.game.map_manager import MapManager
from src.repositories.ground_items_repository import GroundItemsRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.services.npc.npc_death_service import NPCDeathService
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def rewards(redis_client, monkeypatch):
    """Mundo con repositorios concretos y sólo los emisores de red simulados.

    Returns:
        Mundo y fábrica de NPCs muertos, cada prueba con Redis exclusivo.
    """
    monkeypatch.setattr("src.services.npc.rewards.settlement.require_durable", AsyncMock())
    maps = MapManager(GroundItemsRepository(redis_client))
    player, npcs = PlayerRepository(redis_client), NPCRepository(redis_client)
    broadcast, respawn, random_spawn = AsyncMock(), AsyncMock(), AsyncMock()
    senders = {}
    for user in (1, 2, 3):
        await redis_client.hset(
            RedisKeys.player_user_stats(user),
            mapping={
                "min_hp": "100",
                "max_hp": "100",
                "min_mana": "100",
                "max_mana": "100",
                "min_sta": "100",
                "max_sta": "100",
                "gold": "0",
                "experience": "100",
                "level": "10",
                "elu": "1000",
                "class_id": "3",
            },
        )
        await player.set_position(user, 40 + user, 50, 2, 3)
        await redis_client.hset(
            RedisKeys.player_stats(user),
            mapping={"strength": "10", "intelligence": "10", "constitution": "10"},
        )
        await redis_client.hset(
            RedisKeys.player_skills(user), mapping={"points": "0", "points_granted_through": "10"}
        )
        sender = AsyncMock()
        sender.connection.capabilities.enabled = 0
        senders[user] = sender
        maps.add_player(2, user, sender, f"user{user}")
    service = NPCDeathService(
        maps,
        npcs,
        player,
        broadcast,
        npc_respawn_service=respawn,
        random_spawn_service=random_spawn,
    )
    monkeypatch.setattr(
        service.loot_table_service,
        "roll",
        lambda _npc: (
            [(12, 20), (15, 1)] if not _npc.is_tamed and not _npc.summoned_by_user_id else []
        ),
    )

    async def spawn(*, x=50, hp=0, level=10, tamed=False, summoned=0):
        npc = await npcs.create_npc_instance(
            npc_id=505,
            char_index=10000 + x,
            map_id=2,
            x=x,
            y=50,
            heading=3,
            name="Goblin",
            description="Fixture",
            body_id=14,
            head_id=0,
            hp=hp,
            max_hp=100,
            level=level,
            is_hostile=True,
            is_attackable=True,
            respawn_time=60,
            respawn_time_max=120,
            gold_min=50000,
            gold_max=50000,
            loot_profile="humanoid",
            is_tamed=tamed,
            summoned_by_user_id=summoned,
        )
        maps.add_npc(2, npc)
        if hp <= 0:
            await redis_client.hset(
                RedisKeys.npc_instance(npc.instance_id),
                mapping={
                    "death_state": "pending",
                    "death_killer": "1",
                    "death_at": str(time.time()),
                },
            )
        return npc

    return SimpleNamespace(
        client=redis_client,
        player=player,
        npcs=npcs,
        maps=maps,
        service=service,
        senders=senders,
        broadcast=broadcast,
        respawn=respawn,
        random_spawn=random_spawn,
        spawn=spawn,
    )
