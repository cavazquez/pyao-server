"""Inspección y cambios de personajes, con identidad y estado persistidos reales."""

import json

import pytest

from src.services.classic_chat.context import ChatCommandError
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("/INFO Jugador", "Jugador"),
        ("/STAT Jugador", "max_hp: 500"),
        ("/BAL Jugador", "1000"),
        ("/INV Jugador", "Espada Larga"),
        ("/BOV Jugador", "Espada Larga"),
        ("/SLOT Jugador 1", "Espada Larga"),
        ("/SKILLS Jugador", "talar"),
        ("/LASTEMAIL Jugador", "example.invalid"),
        ("/NICK2IP Jugador", "127.0.0.2"),
        ("/LASTIP Jugador", "127.0.0.2"),
        ("/DONDE Jugador", "50"),
        ("/IP2NICK 127.0.0.2", "Jugador"),
        ("/ONLINEGM", "Operador"),
        ("/ONLINEMAP 2", "Jugador"),
        ("/NENE 2", "Murciélago"),
        ("/CC 1", "Catálogo NPC"),
        ("/PISO", "suelo"),
        ("/HORA", "UTC"),
        ("/DUMPSECURITY", "3 sesiones"),
    ],
)
async def test_queries_return_real_private_data(chat_world, command, expected):
    """Queries return real private data."""
    world = chat_world
    await world.redis.hset(RedisKeys.player_inventory(2), "slot_1", "2:1")
    await world.redis.hset(RedisKeys.bank(2), "slot_1", "2:1")
    text = await world.run(command)
    assert expected in text
    assert not world.senders[2].lines
    assert not world.senders[3].lines


@pytest.mark.asyncio
async def test_description_and_all_mod_variants_persist_and_publish(chat_world):
    """Description and all mod variants persist and publish."""
    world = chat_world
    assert "actualizada" in await world.run("/DESC Una descripción", user=2)
    assert (
        await world.redis.hget(RedisKeys.player_user_stats(2), "description") == "Una descripción"
    )
    assert "actualizada" in await world.run("/SETDESC Jugador@Otra descripción")
    before = len(world.senders[2].connection.send.call_args_list)
    variants = [
        ("BODY 2", RedisKeys.account_data("Jugador"), "char_body", "2"),
        ("HEAD 2", RedisKeys.account_data("Jugador"), "char_head", "2"),
        ("CLASE Ladrón", RedisKeys.account_data("Jugador"), "char_job", "5"),
        ("RAZA Elfo", RedisKeys.account_data("Jugador"), "char_race", "2"),
        ("SEX Mujer", RedisKeys.account_data("Jugador"), "char_gender", "2"),
        ("SKILLS Talar 75", RedisKeys.player_skills(2), "level:talar", "75"),
        ("SKILLSLIBRES 15", RedisKeys.player_skills(2), "points", "15"),
        ("ORO 1250", RedisKeys.player_user_stats(2), "gold", "1250"),
        ("AGREGAR -50", RedisKeys.player_user_stats(2), "gold", "1200"),
        ("CRI 80", RedisKeys.player_user_stats(2), "criminal_kills", "80"),
        ("CIU 4", RedisKeys.player_user_stats(2), "citizen_kills", "4"),
        ("NOB 100", RedisKeys.player_user_stats(2), "rep_noble", "100"),
        ("ASE 5", RedisKeys.player_user_stats(2), "rep_murderer", "5"),
        ("VIDA 300", RedisKeys.player_user_stats(2), "max_hp", "300"),
        ("MANA 80", RedisKeys.player_user_stats(2), "min_mana", "80"),
        ("ENERGIA 75", RedisKeys.player_user_stats(2), "min_sta", "75"),
        ("LEVEL 30", RedisKeys.player_user_stats(2), "level", "30"),
        ("EXP 100", RedisKeys.player_user_stats(2), "experience", "100"),
        ("POSS 3-40-40", RedisKeys.player_position(2), "map", "3"),
    ]
    for arguments, key, field, expected in variants:
        text = await world.run("/MOD Jugador " + arguments)
        assert "actualizad" in text.lower(), (arguments, text)
        assert await world.redis.hget(key, field) == expected, arguments
    assert len(world.senders[2].connection.send.call_args_list) > before


@pytest.mark.asyncio
async def test_permissions_are_rechecked_inside_commit(chat_world):
    """Permissions are rechecked inside commit."""
    ctx = chat_world.ctx("/MOD", "Jugador ORO 200")
    await chat_world.redis.hset(RedisKeys.account_data("Operador"), "is_gm", "0")
    key = RedisKeys.player_user_stats(2)
    result = await ctx.commit(
        (Resource(key, "hash"),),
        {},
        lambda _snapshot: Decision({"applied": True}, {key: {"gold": "200"}}),
    )
    assert not result["applied"]
    assert await chat_world.redis.hget(key, "gold") == "1000"


@pytest.mark.asyncio
async def test_account_changes_and_penalties_preserve_identity(chat_world):
    """Account changes and penalties preserve identity."""
    world = chat_world
    assert "actualizado" in await world.run("/AEMAIL Offline-nuevo@example.invalid")
    assert (
        await world.redis.hget(RedisKeys.account_data("Offline"), "email")
        == "nuevo@example.invalid"
    )
    assert "transferida" in await world.run("/APASS Offline@Jugador")
    assert await world.redis.hget(
        RedisKeys.account_data("Offline"), "password_hash"
    ) == await world.redis.hget(RedisKeys.account_data("Jugador"), "password_hash")
    assert "conserva su partida" in await world.run("/ANAME Offline@Renombrado")
    assert (await world.deps.account_repo.get_account_by_user_id(4))["username"] == "Renombrado"
    assert await world.deps.account_repo.get_account("Offline") is None
    assert "registrada" in await world.run("/ADVERTENCIA Jugador@Motivo de prueba")
    rows = await world.redis.hgetall("moderation:penalties:2")
    identifier = next(iter(rows))
    assert "Motivo de prueba" in await world.run("/PENAS Jugador", user=3)
    assert "retirada" in await world.run("/BORRARPENA Jugador@" + identifier)
    assert json.loads(await world.redis.hget("moderation:penalties:2", identifier))["removed"]
    assert "Sin prontuario" in await world.run("/PENAS Jugador", user=3)


@pytest.mark.asyncio
async def test_invalid_object_selection_is_rejected_before_mutation(chat_world):
    """Invalid object selection is rejected before mutation."""
    ctx = chat_world.ctx("/RESETINV")
    with pytest.raises(ChatCommandError, match="selecciona"):
        await ctx.npc()
