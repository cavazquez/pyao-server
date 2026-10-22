"""Mundo descartable con repositorios, servicios y paquetes reales para comandos."""

import sys
from copy import deepcopy
from dataclasses import fields
from functools import cache
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest_asyncio
from argon2 import PasswordHasher

from src.command_handlers.talk_handler import TalkCommandHandler
from src.commands.talk_command import TalkCommand
from src.config.config_manager import ConfigManager
from src.core.dependency_container import DependencyContainer
from src.economy.merchant_stock import catalog_key
from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.models.npc_catalog import NPCCatalog
from src.models.spell_catalog import SpellCatalog
from src.network.capabilities import SUPPORTED_CAPABILITIES
from src.repositories.account_repository import USER_ACCOUNT_INDEX, AccountRepository
from src.repositories.bank_repository import BankRepository
from src.repositories.clan_repository import ClanRepository
from src.repositories.ground_items_repository import GroundItemsRepository
from src.repositories.merchant_repository import MerchantRepository
from src.repositories.party_repository import PartyRepository
from src.repositories.server_repository import ServerRepository
from src.repositories.spellbook_repository import SpellbookRepository
from src.services.action_cadence import ActionCadence
from src.services.clan.clan_service import ClanService
from src.services.classic_chat.context import ChatContext
from src.services.classic_chat.service import ClassicChatService
from src.services.map.player_map_service import PlayerMapService
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.services.npc.npc_respawn_service import NPCRespawnService
from src.services.npc.npc_service import NPCService
from src.services.party_service import PartyService
from src.services.player.player_death_service import PlayerDeathService
from src.services.world.world_state import WorldStateService
from src.utils import durability
from src.utils.redis_config import RedisKeys


@cache
def password_hash(user):
    """Genera una credencial sintética reutilizable para cada actor del mundo de prueba."""
    return PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash(f"Fixture-{user}")


class CapturingSender(MessageSender):
    def __init__(self, user) -> None:
        """Construye un emisor real con transporte aislado y mensajes capturados."""
        peer = SimpleNamespace(
            send=AsyncMock(),
            flush=AsyncMock(),
            close=MagicMock(),
            address=(f"127.0.0.{user}", 20000 + user),
            is_authenticated=True,
            capabilities=SimpleNamespace(enabled=SUPPORTED_CAPABILITIES),
            state_epoch=f"{user:032x}",
            state_sequence=0,
            state_topics=set(),
            state_pages={},
            session_redis=None,
            session_user_id=user,
        )
        super().__init__(peer)
        self.lines = []

    async def send_console_msg(self, message, *args: object, **kwargs: object):
        self.lines.append(message)
        await super().send_console_msg(message, *args, **kwargs)

    async def send_multiline_console_msg(self, message):
        self.lines.append(message)
        await super().send_multiline_console_msg(message)


class ChatWorld:
    def __init__(self, deps, senders, stops) -> None:
        """Conserva las dependencias y evidencias del mundo descartable."""
        self.deps, self.senders, self.stops = deps, senders, stops
        self.redis = deps.redis_client.redis
        self.service = ClassicChatService(deps)

    def ctx(self, command, arguments="", user=1):
        return ChatContext(self.deps, user, self.senders[user], command, arguments, user == 1)

    async def run(self, text, user=1):
        self.deps.test_clock[0] += 1
        sender = self.senders[user]
        start = len(sender.lines)
        await self.service.execute(user, text, sender)
        return "\n".join(sender.lines[start:])

    async def talk(self, text, user=1):
        deps, sender = self.deps, self.senders[user]
        start = len(sender.lines)
        handler = TalkCommandHandler(
            deps.player_repo,
            deps.account_repo,
            deps.map_manager,
            deps.game_tick,
            sender,
            deps.clan_service,
            deps.trade_service,
            deps.npc_service,
            deps.summon_service,
            {"username": deps.map_manager.get_player_username(user)},
            classic_deps=deps,
        )
        result = await handler.handle(TalkCommand(user, text))
        assert result.success
        return "\n".join(sender.lines[start:])

    async def select_npc(self, npc_id, user=2, x=51, y=51):
        npc = await self.deps.npc_service.spawn_npc(npc_id, 2, x, y)
        assert npc is not None
        await self.redis.hset(
            f"chat:target:{user}",
            mapping={
                "npc": npc.instance_id,
                "index": str(npc.char_index),
                "map": "2",
                "x": str(x),
                "y": str(y),
                "user": "0",
            },
        )
        return npc


async def _populate_accounts(base, client, maps, senders):
    """Prepara identidades, índices y posiciones de los cuatro actores."""
    names = {1: "Operador", 2: "Jugador", 3: "Invitado", 4: "Offline"}
    for user, name in names.items():
        if user > 2:
            await client.hset(
                RedisKeys.player_user_stats(user), mapping=await base.player.get_stats(2)
            )
            await client.hset(
                RedisKeys.player_stats(user),
                mapping=await client.hgetall(RedisKeys.player_stats(2)),
            )
            await client.hset(
                RedisKeys.player_skills(user),
                mapping=await client.hgetall(RedisKeys.player_skills(2)),
            )
            await client.hset(
                RedisKeys.player_position(user),
                mapping={"map": "2", "x": str(48 + user), "y": "52", "heading": "3"},
            )
        await client.hset(
            RedisKeys.account_data(name),
            mapping={
                "username": name,
                "user_id": str(user),
                "is_gm": "1" if user == 1 else "0",
                "char_job": "4",
                "char_race": "1",
                "char_gender": "1",
                "char_body": "1",
                "char_head": "1",
                "char_home": "1",
                "email": f"{name.lower()}@example.invalid",
                "password_hash": password_hash(user),
            },
        )
        await client.hset(USER_ACCOUNT_INDEX, str(user), name)
        await client.set(RedisKeys.account_id_by_username(name), str(user))
        if user in senders:
            pos = await base.player.get_position(user)
            maps.add_player(2, user, senders[user], name)
            maps.update_player_tile(user, 2, 0, 0, pos["x"], pos["y"])


def _populate_services(deps, base, maps, terrain, senders):
    """Conecta los servicios reales que comparten el mundo de pruebas."""
    deps.broadcast_service = MultiplayerBroadcastService(maps, base.player, deps.account_repo)
    deps.player_map_service = PlayerMapService(
        base.player, deps.account_repo, maps, deps.broadcast_service, map_resources=terrain
    )
    deps.player_death_service = PlayerDeathService(
        maps, base.player, deps.broadcast_service, base.inventory, base.catalog, deps.account_repo
    )
    NPCService.reset_instance()
    deps.npc_service = NPCService(base.npcs, deps.npc_catalog, maps, deps.broadcast_service)
    deps.npc_service._next_char_index = 10002
    deps.npc_respawn_service = NPCRespawnService(deps.npc_service)
    deps.clan_service = ClanService(deps.clan_repo, base.player, senders[1], map_manager=maps)
    deps.party_service = PartyService(
        deps.party_repo, base.player, senders[1], map_manager=maps, account_repo=deps.account_repo
    )


@pytest_asyncio.fixture
async def chat_world(mechanics_world, monkeypatch):
    """Sustituye sólo transporte y AOF, cuya barrera se prueba con Redis real.

    Yields:
        Mundo de tres conexiones y una cuenta desconectada, sin servidor externo.
    """
    saved_config = deepcopy(ConfigManager._config)
    base, client = mechanics_world, mechanics_world.redis
    # Las fachadas reales conservan WATCH/EXEC/recibos. Fakeredis no implementa WAITAOF.
    original = durability.require_durable
    durable = AsyncMock()
    for name, module in list(sys.modules.items()):
        if name.startswith("src.") and getattr(module, "require_durable", None) is original:
            monkeypatch.setattr(module, "require_durable", durable)
    deps = SimpleNamespace(**{field.name: None for field in fields(DependencyContainer)})
    deps.redis_client, deps.player_repo, deps.inventory_repo = client, base.player, base.inventory
    deps.npc_repo, deps.item_catalog, deps.npc_catalog = base.npcs, base.catalog, NPCCatalog()
    deps.account_repo, deps.bank_repo = AccountRepository(client), BankRepository(client)
    deps.merchant_repo, deps.server_repo = MerchantRepository(client), ServerRepository(client)
    deps.spellbook_repo, deps.spell_catalog = SpellbookRepository(client), SpellCatalog()
    deps.clan_repo, deps.party_repo = ClanRepository(client), PartyRepository(client)
    await deps.clan_repo.initialize()
    await deps.party_repo.initialize()
    maps = MapManager(GroundItemsRepository(client))
    maps._map_sizes.update({1: (100, 100), 2: (100, 100), 3: (100, 100), 66: (100, 100)})
    deps.map_manager = maps
    senders = {user: CapturingSender(user) for user in (1, 2, 3)}
    await _populate_accounts(base, client, maps, senders)
    maps.add_npc(2, base.npc)
    terrain = base.terrain
    terrain.workshops = {}
    terrain.has_tree = lambda *_: False
    terrain.has_mine = lambda *_: False
    terrain.is_blocked = lambda mid, x, y: maps.tile_overrides.get((mid, x, y), {}).get(
        "blocked", False
    )
    deps.map_resources_service = terrain
    _populate_services(deps, base, maps, terrain, senders)
    deps.trade_service = SimpleNamespace(metadata_publisher=None)
    deps.test_clock = [0.0]
    deps.action_cadence = ActionCadence(clock=lambda: deps.test_clock[0])
    stops = []
    deps.admin_control = stops.append
    deps.npc_death_service = SimpleNamespace(quest_service=None)
    deps.world_state = WorldStateService(deps)
    # Política comercial real usada por RESETINV; no se relee ningún TOML al reponer.
    await client.hset(
        catalog_key(2),
        mapping={
            "version": "1",
            "items": "[[2,20,2],[38,10,1]]",
            "interval_seconds": "60",
            "last_restock": "0",
        },
    )
    try:
        yield ChatWorld(deps, senders, stops)
    finally:
        deps.npc_respawn_service.cancel_all_respawns()
        await deps.player_death_service.close()
        await deps.world_state.close()
        NPCService.reset_instance()
        ConfigManager._config = saved_config
