"""Liquida una muerte persistida antes de retirar la instancia o programar su respawn."""

import asyncio
import logging
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from src.services.npc.loot_table_service import LootTableService
from src.services.npc.rewards.experience import ExperienceComponent
from src.services.npc.rewards.settlement import settle_rewards

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.npc import NPC
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.expansion.quests import QuestService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.npc_respawn_service import NPCRespawnService
    from src.services.npc.random_spawn_service import RandomSpawnService
    from src.services.party_service import PartyService

logger = logging.getLogger(__name__)
DROP_RADIUS = 4
RECOVERY_BATCH = 128


class NPCDeathService:
    """Oro, objetos, XP, niveles y puntos se confirman juntos; la UI se publica después."""

    def __init__(
        self,
        map_manager: MapManager,
        npc_repo: NPCRepository,
        player_repo: PlayerRepository,
        broadcast_service: MultiplayerBroadcastService,
        loot_table_service: LootTableService | None = None,
        item_catalog: ItemCatalog | None = None,
        npc_respawn_service: NPCRespawnService | None = None,
        party_service: PartyService | None = None,
        random_spawn_service: RandomSpawnService | None = None,
    ) -> None:
        """Conserva dependencias y exclusión por instancia sin retener locks ya liberados."""
        self.map_manager, self.npc_repo, self.player_repo = map_manager, npc_repo, player_repo
        self.broadcast_service = broadcast_service
        self.loot_table_service = loot_table_service or LootTableService()
        self.item_catalog = item_catalog or self.loot_table_service.catalog
        self.npc_respawn_service, self.party_service = npc_respawn_service, party_service
        self.random_spawn_service = random_spawn_service
        self.quest_service: QuestService | None = None
        self._experience = ExperienceComponent(self)
        self._locks: WeakValueDictionary[str, asyncio.Lock] = WeakValueDictionary()
        self._recovery_cursor = 0

    def _drop_positions(self, npc: NPC) -> tuple[tuple[int, int], ...]:
        candidates = [
            (x, y)
            for x in range(npc.x - DROP_RADIUS, npc.x + DROP_RADIUS + 1)
            for y in range(npc.y - DROP_RADIUS, npc.y + DROP_RADIUS + 1)
            if self.map_manager.can_move_to(npc.map_id, x, y)
        ]
        return tuple(
            sorted(candidates, key=lambda p: (max(abs(p[0] - npc.x), abs(p[1] - npc.y)), p))
        )

    async def handle_npc_death(
        self,
        npc: NPC,
        killer_user_id: int,
        experience: int,
        message_sender: MessageSender | None,
        death_reason: str = "combate",
    ) -> None:
        """Lee la instancia actual y no paga ni retira una instancia viva/ya retirada."""
        lock = self._locks.setdefault(npc.instance_id, asyncio.Lock())
        async with lock:
            current = await self.npc_repo.get_npc(npc.instance_id)
            if current is None or current.hp > 0:
                return
            state = await self.npc_repo.redis.hgetall(f"npc:instance:{npc.instance_id}")
            killer = int(state.get("death_killer", killer_user_id))
            positions = self._drop_positions(current)
            result = await self.map_manager.apply_ground_operation(
                current.map_id,
                current.x,
                current.y,
                self.npc_repo.redis.redis,
                lambda: settle_rewards(
                    self.npc_repo.redis.redis,
                    current,
                    killer,
                    experience,
                    self.loot_table_service,
                    positions,
                ),
                broadcast_service=self.broadcast_service,
                ground_positions=positions,
            )
            if not result.get("settled"):
                return
            if result["applied"]:
                await self._experience.publish(current, killer, result, message_sender)
                if self.quest_service and killer > 0:
                    await self.quest_service.record_kill(current, killer)
            if state.get("skip_respawn") == "1":
                # Un cadáver retenido al iniciar ya no pertenece al mundo regenerado.
                # Su CharIndex puede haber sido reutilizado por un NPC vivo.
                self.map_manager.remove_npc(current.map_id, current.instance_id)
            else:
                await self._remove_npc_from_game(current)
            await self.npc_repo.remove_npc(current.instance_id)
            if self.random_spawn_service and state.get("skip_respawn") != "1":
                await self.random_spawn_service.on_random_npc_death(current.instance_id)
            if self.npc_respawn_service and state.get("skip_respawn") != "1":
                await self.npc_respawn_service.schedule_respawn(current)
            logger.info("Muerte de NPC %s liquidada, causa=%s", current.instance_id, death_reason)

    async def _remove_npc_from_game(self, npc: NPC) -> None:
        if npc.snd3 > 0:
            await self.broadcast_service.broadcast_play_wave(
                map_id=npc.map_id, wave_id=npc.snd3, x=npc.x, y=npc.y
            )
        if npc.fx > 0:
            await self.broadcast_service.broadcast_create_fx(
                map_id=npc.map_id, char_index=npc.char_index, fx=npc.fx, loops=1
            )
        self.map_manager.remove_npc(npc.map_id, npc.instance_id)
        await self.broadcast_service.broadcast_character_remove(
            map_id=npc.map_id, char_index=npc.char_index
        )

    async def recover_pending(self, *, all_records: bool = False, bootstrap: bool = False) -> None:
        """Recupera caídas entre HP y liquidación, también antes de regenerar NPCs al iniciar."""
        redis = self.npc_repo.redis.redis
        while True:
            self._recovery_cursor, keys = await redis.scan(
                self._recovery_cursor, match="npc:instance:*", count=RECOVERY_BATCH
            )
            async with redis.pipeline(transaction=False) as pipe:
                for key in keys:
                    pipe.hgetall(key)
                states = await pipe.execute()
            for state in states:
                if (
                    state.get("death_state") not in {"pending", "complete"}
                    or int(state.get("hp", 1)) > 0
                ):
                    continue
                npc = await self.npc_repo.get_npc(state["instance_id"])
                if npc:
                    if bootstrap:
                        await redis.hset(f"npc:instance:{npc.instance_id}", "skip_respawn", "1")
                    await self.handle_npc_death(
                        npc,
                        int(state.get("death_killer", 0)),
                        npc.level * 10,
                        None,
                        death_reason="recuperación durable",
                    )
            if not all_records or self._recovery_cursor == 0:
                return
