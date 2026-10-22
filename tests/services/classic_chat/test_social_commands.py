"""Canales privados, soporte, elecciones y propiedad de criaturas entre jugadores."""

import json
import time

import pytest

from src.services.classic_chat.collective import finish_election_for
from src.services.combat.npc_claims import claim_rejection, sharing_key
from src.utils.redis_config import RedisKeys


def chat_messages(sender):
    """Decodifica los mensajes estructurados emitidos al destinatario."""
    return [
        json.loads(call.args[0][4:])["data"]
        for call in sender.connection.send.call_args_list
        if call.args[0][0] == 248 and json.loads(call.args[0][4:])["kind"] == "chat"
    ]


@pytest.mark.asyncio
async def test_reports_panel_clear_and_denounce_preferences_are_private(chat_world):
    """Reports panel clear and denounce preferences are private."""
    world = chat_world
    for command, kind in (
        ("/GM", "help"),
        ("/ROL", "role"),
        ("/_BUG", "bug"),
        ("/DENUNCIAR", "denounce"),
    ):
        assert "registrada" in await world.run(command + " Solicitud privada", user=2)
        assert await world.redis.hlen("chat:reports:" + kind) == 1
    assert not world.senders[3].lines
    assert "Solicitud privada" in await world.run("/SHOW SOS")
    assert "Solicitud privada" in await world.run("/SHOW DENUNCIAS")
    assert "Solicitud privada" in await world.run("/SHOW BUGS")
    assert "Solicitud privada" in await world.run("/SHOW ROL")
    assert "Panel GM" in await world.run("/PANELGM")
    await world.run("/REM Nota del operador")
    assert await world.redis.hlen("moderation:comments:1") == 1
    await world.run("/BORRAR SOS")
    assert not await world.redis.hlen("chat:reports:help")
    assert await world.redis.hlen("chat:reports:bug") == 1
    await world.run("/SILENCIAR Jugador")
    assert "silenciadas" in await world.run("/DENUNCIAR No debe guardarse", user=2)
    assert await world.redis.hlen("chat:reports:denounce") == 1
    assert "registrada" in await world.run("/GM Ayuda disponible", user=2)
    await world.run("/DENUNCIAS")
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "gm_denounces") == "0"


@pytest.mark.asyncio
async def test_inquiry_has_one_vote_per_player_and_gm_only_administration(chat_world):
    """Inquiry has one vote per player and gm only administration."""
    world = chat_world
    assert "Sólo un GM" in await world.run("/ENCUESTA CREAR ¿Sí?|Sí|No", user=2)
    assert "creada" in await world.run("/ENCUESTA CREAR ¿Cambiar horario?|Sí|No")
    state = await world.redis.hgetall("world:inquiry")
    assert "¿Cambiar horario?" in await world.run("/ENCUESTA", user=2)
    assert "registrado" in await world.run("/ENCUESTA 1", user=2)
    assert "Ya has votado" in await world.run("/ENCUESTA 2", user=2)
    assert await world.redis.hget(f"world:inquiry:{state['id']}:votes", "2") == "1"
    await world.run("/ENCUESTA CERRAR")
    assert await world.redis.hget("world:inquiry", "active") == "0"


@pytest.mark.asyncio
async def test_council_and_admin_message_audiences_and_rgb(chat_world):
    """Council and admin message audiences and rgb."""
    world = chat_world
    for user, fields in (
        (1, {"faction_id": "royal"}),
        (2, {"faction_id": "royal", "faction_council": "1"}),
        (3, {"faction_id": "chaos", "criminal": "1"}),
    ):
        await world.redis.hset(RedisKeys.player_user_stats(user), mapping=fields)
    await world.run("/BMSG Consejo privado", user=2)
    assert any(message["text"] == "Consejo privado" for message in chat_messages(world.senders[1]))
    assert not chat_messages(world.senders[3])
    for command, recipients in (
        ("/GMSG", {1}),
        ("/REALMSG", {1, 2}),
        ("/CAOSMSG", {3}),
        ("/CIUMSG", {1, 2}),
        ("/CRIMSG", {3}),
        ("/MAPMSG", {1, 2, 3}),
        ("/RMSG", {1, 2, 3}),
        ("/SMSG", {1, 2, 3}),
    ):
        for sender in world.senders.values():
            sender.lines.clear()
        await world.run(command + " Aviso")
        actual = {
            user
            for user, sender in world.senders.items()
            if any("Aviso" in line for line in sender.lines)
        }
        assert actual == recipients, command
    assert "Jugador" in await world.run("/ONLINEREAL")
    assert "Invitado" in await world.run("/ONLINECAOS")
    await world.run("/CHATCOLOR 10 20 30")
    await world.talk("Color del operador")
    assert chat_messages(world.senders[2])[-1]["color"] == [10, 20, 30]
    await world.run("/CHATCOLOR")
    assert await world.redis.hget(RedisKeys.player_user_stats(1), "chat_rgb") == "0,255,0"


@pytest.mark.asyncio
async def test_classic_clan_commands_election_and_observer_preserve_membership(chat_world):
    """Classic clan commands election and observer preserve membership."""
    world = chat_world
    assert "fundador" in await world.run("/FUNDARCLANGM Custodios")
    clan = await world.deps.clan_repo.get_user_clan(1)
    for name, user in (("Jugador", 2), ("Invitado", 3)):
        await world.deps.clan_service.invite_to_clan(1, name)
        group, _message = await world.deps.clan_service.accept_invitation(user)
        assert group is not None
    assert "Jugador" in await world.run("/ONLINECLAN", user=3)
    assert "Invitado" in await world.run("/MIEMBROSCLAN Custodios")
    assert "Jugador" in await world.run("/ONCLAN Custodios")
    await world.run("/CMSG Mensaje interno", user=2)
    assert any(message["text"] == "Mensaje interno" for message in chat_messages(world.senders[3]))
    assert "abiertas" in await world.run("/ELECCIONES ABRIR")
    assert "contabilizado" in await world.run("/VOTO Jugador")
    assert "contabilizado" in await world.run("/VOTO Jugador", user=2)
    assert "Ya has votado" in await world.run("/VOTO Operador", user=2)
    await world.redis.hset(f"clan:{clan.clan_id}:election", "ends", str(time.time() - 1))
    await finish_election_for(world.deps, clan.clan_id)
    group = await world.deps.clan_repo.get_user_clan(2)
    assert group.leader_id == 2
    assert len(group.members) == 3
    await world.run("/RAJARCLAN Invitado")
    assert await world.deps.clan_repo.get_user_clan(3) is None
    assert set((await world.deps.clan_repo.get_user_clan(2)).members) == {1, 2}
    assert "fundador" in await world.run("/RAJARCLAN Jugador")


@pytest.mark.asyncio
async def test_clan_chat_observer_requires_live_gm_role(chat_world):
    """Clan chat observer requires live gm role."""
    world = chat_world
    await world.redis.hset(RedisKeys.player_skills(2), "level:liderazgo", "100")
    clan, _message = await world.deps.clan_service.create_clan(2, "OtroClan", username="Jugador")
    assert clan is not None
    await world.run("/SHOWCMSG")
    await world.run("/CMSG Observable", user=2)
    assert any("OtroClan" in message["text"] for message in chat_messages(world.senders[1]))
    before = len(chat_messages(world.senders[1]))
    await world.redis.hset(RedisKeys.account_data("Operador"), "is_gm", "0")
    await world.run("/CMSG Ya no observable", user=2)
    assert len(chat_messages(world.senders[1])) == before


@pytest.mark.asyncio
async def test_sharing_npc_grants_and_revokes_claim_permission(chat_world):
    """Sharing npc grants and revokes claim permission."""
    world = chat_world
    await world.redis.hset("chat:target:2", mapping={"user": "3", "npc": "", "map": "2"})
    assert "compartes" in await world.run("/COMPARTIRNPC", user=2)
    assert await world.redis.smembers(sharing_key(3)) == {"2"}
    npc = {"map_id": "2", "combat_owner": "2", "claim_until": str(time.time() + 20)}
    assert not claim_rejection({sharing_key(3): {"2"}}, npc, 3, time.time())
    assert "dejado" in await world.run("/NOCOMPARTIRNPC", user=2)
    assert not await world.redis.smembers(sharing_key(3))
    assert "otro jugador" in claim_rejection({sharing_key(3): set()}, npc, 3, time.time())


@pytest.mark.asyncio
async def test_sentinel_challenge_worker_reply_and_failure_are_persisted(chat_world):
    """Sentinel challenge worker reply and failure are persisted."""
    world = chat_world
    await world.run("/CENTINELAACTIVADO")
    await world.redis.hset(RedisKeys.player_user_stats(2), "work_last_at", str(time.time()))
    worker = world.deps.world_state.classic_maintenance
    await worker.tick()
    state = await world.redis.hgetall("security:sentinel:2")
    assert state["answered"] == "0"
    assert len(state["code"]) == 4
    wrong = str(int(state["code"]) + 1)
    assert "incorrecto" in await world.run("/CENTINELA " + wrong, user=2)
    assert "confirmado" in await world.run("/CENTINELA " + state["code"], user=2)
    await worker.tick()
    assert not await world.redis.smembers("security:sentinel:active")
    await world.redis.hset("security:sentinel:policy", "next_at", "0")
    await worker.tick()
    await world.redis.hset("security:sentinel:2", "until", str(time.time() - 1))
    await worker.tick()
    assert await world.redis.hget("security:sentinel:failures", "2") == "1"
    assert await world.redis.hlen("chat:reports:denounce") == 1
