"""Mundo Redis descartable para comprobar mecánicas completas con datos reales."""

from dataclasses import asdict
from types import SimpleNamespace

import pytest_asyncio

from src.models.crafting_data_loader import CraftingDataLoader
from src.models.item_catalog import ItemCatalog
from src.models.npc import NPC
from src.models.skill_data_loader import SkillDataLoader
from src.models.skills import CATALOG
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def mechanics_world(redis_client):
    """Carga reglas y recetas, dos jugadores y una criatura con progreso independiente.

    Returns:
        Repositorios reales, terreno controlable y estados iniciales en Redis.
    """
    await SkillDataLoader(redis_client).load()
    await CraftingDataLoader(redis_client).load()
    player, inventory = PlayerRepository(redis_client), InventoryRepository(redis_client)
    for uid in (1, 2):
        await redis_client.hset(
            RedisKeys.player_user_stats(uid),
            mapping={
                "level": "40",
                "experience": "0",
                "min_hp": "500",
                "max_hp": "500",
                "min_mana": "50",
                "max_mana": "100",
                "min_sta": "100",
                "max_sta": "100",
                "safe_mode": "0",
                "class_id": "4" if uid == 1 else "5",
                "gold": "1000",
            },
        )
        await redis_client.hset(
            RedisKeys.player_stats(uid),
            mapping={
                "strength": "20",
                "agility": "20",
                "intelligence": "20",
                "charisma": "20",
                "constitution": "20",
            },
        )
        await redis_client.hset(
            RedisKeys.player_position(uid),
            mapping={"map": "2", "x": "50", "y": str(49 + uid), "heading": "2"},
        )
        await redis_client.hset(
            RedisKeys.player_hunger_thirst(uid), mapping={"min_hunger": "100", "min_water": "100"}
        )
        await player.set_skills(uid, **{d.key: 0 for d in CATALOG if d.key})
        await redis_client.hset(
            RedisKeys.player_skills(uid),
            mapping={"assigned_points": "10", "points": "0", "points_granted_through": "40"},
        )
    npc = NPC(
        500,
        10001,
        "animal",
        2,
        51,
        50,
        3,
        "Murciélago",
        "",
        9,
        0,
        500,
        500,
        1,
        True,
        True,
        domable=400,
    )
    await redis_client.hset(
        RedisKeys.npc_instance(npc.instance_id), mapping={k: str(v) for k, v in asdict(npc).items()}
    )
    await redis_client.sadd(RedisKeys.npc_map_index(2), npc.instance_id)
    terrain = SimpleNamespace(
        has_tree=lambda *_: True,
        has_mine=lambda *_: True,
        has_water=lambda *_: False,
        is_blocked=lambda *_: False,
        has_anvil=lambda *_: True,
        has_forge=lambda *_: True,
    )
    return SimpleNamespace(
        redis=redis_client,
        player=player,
        inventory=inventory,
        terrain=terrain,
        catalog=ItemCatalog(),
        npc=npc,
        npcs=NPCRepository(redis_client),
    )
