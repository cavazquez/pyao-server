"""Controles administrativos reales con límites en los procesos externos."""

import time
from unittest.mock import AsyncMock

import pytest

from src.config.config_manager import config_manager
from src.security.account_bans import is_blocked
from src.security.ip_bans import ip_is_blocked
from src.services.classic_chat.jobs import ClassicActionsEffect
from src.utils.redis_config import RedisKeys


@pytest.mark.asyncio
async def test_access_motd_runtime_settings_and_catalog_reloads(chat_world):
    """Access motd runtime settings and catalog reloads."""
    world = chat_world
    assert "restringido" in await world.run("/HABILITAR")
    assert await world.redis.hget("server:admission", "gm_only") == "1"
    assert "habilitado" in await world.run("/HABILITAR")
    assert "actualizado" in await world.run("/MOTDCAMBIA Bienvenida de prueba")
    assert "Bienvenida de prueba" in await world.run("/MOTD", user=2)
    assert "persistida" in await world.run("/SETINIVAR game.cadence.walk_seconds 0.25")
    assert config_manager.get("game.cadence.walk_seconds") == pytest.approx(0.25)
    assert await world.redis.hget("config:runtime", "game.cadence.walk_seconds") == "0.25"
    assert "editables" in await world.run("/SETINIVAR redis.password false")
    for command in ("/RELOADNPCS", "/RELOADOBJ", "/RELOADHECHIZOS", "/RELOADSINI"):
        assert "Recarga completada" in await world.run(command), command
    assert config_manager.get("game.cadence.walk_seconds") == pytest.approx(0.25)
    assert "confirmadas" in await world.run("/GRABAR")
    assert await world.redis.hget("world:save", "actor") == "1"


@pytest.mark.asyncio
async def test_shutdown_restart_and_configured_update_hook(chat_world, tmp_path):
    """Shutdown restart and configured update hook."""
    world = chat_world
    assert "Apagando" in await world.run("/APAGAR")
    assert "Reiniciando" in await world.run("/REINICIAR")
    assert world.stops == [False, True]
    assert world.senders[1].connection.flush.await_count == 2
    marker = tmp_path / "agent-ran"
    agent = tmp_path / "agent"
    agent.write_text("#!/bin/sh\nset -eu\nprintf ok > " + str(marker) + "\n")
    agent.chmod(0o700)
    config_manager.set("server.autoupdate_hook", str(agent))
    assert "ejecutado correctamente" in await world.run("/AUTOUPDATE")
    assert marker.read_text() == "ok"
    link = tmp_path / "link"
    link.symlink_to(agent)
    config_manager.set("server.autoupdate_hook", str(link))
    assert "debe configurar" in await world.run("/AUTOUPDATE")
    assert world.stops == [False, True]


@pytest.mark.asyncio
async def test_rdb_confirmation_does_not_claim_a_snapshot_before_completion(
    chat_world, monkeypatch
):
    """Rdb confirmation does not claim a snapshot before completion."""
    world = chat_world
    started = int(time.time())
    save = AsyncMock()
    info = AsyncMock(
        side_effect=[
            {"rdb_bgsave_in_progress": 1},
            {
                "rdb_bgsave_in_progress": 0,
                "rdb_last_bgsave_status": "ok",
                "rdb_last_save_time": started,
            },
        ]
    )
    monkeypatch.setattr(world.redis, "bgsave", save)
    monkeypatch.setattr(world.redis, "info", info)
    assert "Snapshot RDB completado" in await world.run("/DOBACKUP")
    assert save.await_count == 1
    assert info.await_count == 2
    assert await world.redis.hget("world:backup", "at") == str(started)


@pytest.mark.asyncio
async def test_ip_bans_moderation_and_clan_admission_are_authoritative(chat_world):
    """Ip bans moderation and clan admission are authoritative."""
    world = chat_world
    assert "bloqueada" in await world.run("/BANIP 127.0.0.3 Prueba")
    assert await ip_is_blocked(world.redis, "127.0.0.3")
    world.senders[3].connection.close.assert_called_once()
    assert "127.0.0.3" in await world.run("/BANIPLIST")
    assert "Verificados 1" in await world.run("/BANIPRELOAD")
    assert "revocado" in await world.run("/UNBANIP 127.0.0.3")
    assert not await ip_is_blocked(world.redis, "127.0.0.3")
    assert "propia conexión" in await world.run("/BANIP 127.0.0.1 Prueba")
    assert "bloque" in (await world.talk("/BAN Offline@Prueba")).lower()
    assert is_blocked(await world.deps.account_repo.get_account("Offline"), prefix="ban_")
    await world.talk("/UNBAN Offline")
    assert not is_blocked(await world.deps.account_repo.get_account("Offline"), prefix="ban_")
    await world.redis.hset(RedisKeys.player_skills(2), "level:liderazgo", "100")
    clan, _text = await world.deps.clan_service.create_clan(2, "Suspendidos", username="Jugador")
    assert clan is not None
    assert "Clan bloqueado" in await world.run("/BANCLAN Suspendidos")
    assert await world.redis.hget(f"clan:{clan.clan_id}:ban", "active") == "1"
    assert is_blocked(await world.deps.account_repo.get_account("Jugador"), prefix="ban_")
    assert "suspendido" in await world.deps.clan_service.invite_to_clan(2, "Invitado")


@pytest.mark.asyncio
async def test_all_teleport_variants_share_safe_arrival_and_do_not_leak_reservations(chat_world):
    """All teleport variants share safe arrival and do not leak reservations."""
    world, maps = chat_world, chat_world.deps.map_manager
    assert "completado" in await world.run("/TELEP YO 3 40 40")
    assert (await world.deps.player_repo.get_position(1))["map"] == 3
    assert "completado" in await world.run("/SUM Jugador")
    assert (await world.deps.player_repo.get_position(2))["map"] == 3
    assert "completado" in await world.run("/IRA Jugador")
    assert "completado" in await world.run("/IRCERCA Invitado")
    assert (await world.deps.player_repo.get_position(1))["map"] == 2
    await world.redis.hset(
        "chat:target:1", mapping={"map": "2", "x": "54", "y": "54", "npc": "", "user": "0"}
    )
    assert "completado" in await world.run("/TELEPLOC")
    assert (await world.deps.player_repo.get_position(1))["x"] == 54
    assert not any(value.startswith("reservation:") for value in maps._tile_occupation.values())


@pytest.mark.asyncio
async def test_jail_offline_deadline_release_and_bulk_disconnect(chat_world):
    """Jail offline deadline release and bulk disconnect."""
    world = chat_world
    key = RedisKeys.player_user_stats(2)
    assert "Condena registrada" in await world.run("/CARCEL Jugador@Prueba@1")
    assert (await world.deps.player_repo.get_position(2))["map"] == 66
    assert float(await world.redis.hget(key, "jail_until")) > time.time()
    assert "rechazada" in await world.run("/TELEP Jugador 3 40 40")
    assert (await world.deps.player_repo.get_position(2))["map"] == 66
    await world.redis.hset(key, "jail_until", str(time.time() - 1))
    await ClassicActionsEffect(world.deps).apply(2, world.deps.player_repo, world.senders[2])
    assert (await world.deps.player_repo.get_position(2))["map"] == 2
    assert await world.redis.hget(key, "jail_pending_return") == "0"
    await world.run("/ECHARTODOSPJS")
    world.senders[2].connection.close.assert_called_once()
    world.senders[3].connection.close.assert_called_once()
    world.senders[1].connection.close.assert_not_called()


@pytest.mark.asyncio
async def test_character_statuses_consultation_nameplate_navigation_and_lifecycle(chat_world):
    """Character statuses consultation nameplate navigation and lifecycle."""
    world = chat_world
    key = RedisKeys.player_user_stats(2)
    for command, field, expected in (
        ("/CONDEN", "criminal", "1"),
        ("/PERDON", "criminal", "0"),
        ("/NOESTUPIDO", "dumb_until", "0"),
    ):
        await world.run(command + " Jugador")
        assert await world.redis.hget(key, field) == expected
    await world.run("/ESTUPIDO Jugador")
    assert float(await world.redis.hget(key, "dumb_until")) > time.time()
    await world.redis.hset("chat:target:1", mapping={"user": "2", "npc": "", "map": "2"})
    assert "iniciada" in await world.run("/CONSULTA")
    assert await world.redis.hget(key, "consultation") == "1"
    assert "terminada" in await world.run("/CONSULTA")
    await world.run("/SHOWNAME")
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "show_name") == "0"
    await world.run("/INVISIBLE")
    assert (
        float(await world.redis.hget(RedisKeys.player_user_stats(1), "invisible_until"))
        > time.time()
    )
    await world.run("/IGNORADO")
    assert 1 not in await world.deps.player_repo.get_positions([1, 2], alive_only=True)
    await world.run("/NAVE")
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "sailing") == "1"
    assert "Ejecución confirmada" in await world.run("/EJECUTAR Jugador")
    assert await world.redis.hget(key, "death_state") == "complete"
    await world.run("/REVIVIR Jugador")
    assert await world.redis.hget(key, "death_state") == "alive"
    await world.run("/ECHAR Invitado")
    world.senders[3].connection.close.assert_called_once()
