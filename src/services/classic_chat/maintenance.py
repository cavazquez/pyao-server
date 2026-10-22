"""Mantenimiento global acotado para elecciones y desafíos de presencia."""

import json
import secrets
import time
from typing import TYPE_CHECKING, cast

from src.services.classic_chat.admin_world import checkpoint
from src.services.classic_chat.collective import ELECTION_INDEX, finish_election_for
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

SENTINEL_POLICY = "security:sentinel:policy"
SENTINEL_ACTIVE = "security:sentinel:active"
SENTINEL_SECONDS = 60
SENTINEL_INTERVAL = 300


class ClassicMaintenance:
    """El worker existe independientemente de los personajes conectados."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Conserva sólo un cursor local; los plazos y resultados viven en Redis."""
        self.deps = deps
        self.cursor = 0
        self.next_snapshot = time.monotonic() + 300

    async def tick(self) -> None:
        """Procesa una página de elecciones y los pocos desafíos activos."""
        redis = self.deps.redis_client.redis
        await require_durable(redis)
        self.cursor, clan_ids = await redis.sscan(ELECTION_INDEX, cursor=self.cursor, count=32)
        for clan_id in clan_ids:
            await finish_election_for(self.deps, int(clan_id))
        if time.monotonic() >= self.next_snapshot:
            for map_id, values in self.deps.map_manager.map_overrides.items():
                if values.get("backup") == "1":
                    await self._save_map(map_id)
            self.next_snapshot = time.monotonic() + 300
        policy = await redis.hgetall(SENTINEL_POLICY)
        for identity in await redis.smembers(SENTINEL_ACTIVE):
            await self._settle_challenge(int(identity), policy.get("active") == "1")
        if policy.get("active") != "1" or float(policy.get("next_at", 0)) > time.time():
            return
        users = self.deps.map_manager.get_all_connected_user_ids()
        if not users:
            return
        async with redis.pipeline(transaction=False) as pipe:
            for user in users:
                pipe.hmget(RedisKeys.player_user_stats(user), ["work_last_at", "min_hp"])
            rows = await pipe.execute()
        choices = [
            user
            for user, row in zip(users, rows, strict=True)
            if float(row[0] or 0) >= time.time() - 5 and int(row[1] or 0) > 0
        ]
        secrets.SystemRandom().shuffle(choices)
        for user in choices:
            account = await self.deps.account_repo.get_account_by_user_id(user)
            if account and account.get("is_gm") != "1":
                await self._challenge(user, account)
                return

    async def _save_map(self, map_id: int) -> None:
        policy_key, saved_key = f"world:map:rules:{map_id}", f"world:map:saved:{map_id}"
        record = checkpoint(self.deps, map_id)

        def decide(snapshot: Snapshot) -> Decision:
            policy = cast("dict[str, str]", snapshot[policy_key])
            if policy.get("backup") != "1":
                return Decision({"applied": False}, {})
            return Decision({"applied": True}, {saved_key: record})

        await transact(
            self.deps.redis_client.redis,
            (Resource(policy_key, "hash"), Resource(saved_key, "string")),
            operation_id(),
            {"map_checkpoint": map_id},
            decide,
        )
        await require_durable(self.deps.redis_client.redis)

    async def _challenge(self, user: int, account: dict[str, str]) -> None:
        redis = self.deps.redis_client.redis
        key, stats_key = f"security:sentinel:{user}", RedisKeys.player_user_stats(user)
        profile_key = RedisKeys.account_data(account["username"])
        code, now = str(1000 + secrets.randbelow(9000)), time.time()

        def decide(snapshot: Snapshot) -> Decision:
            state = cast("dict[str, str]", snapshot[SENTINEL_POLICY])
            stats = cast("dict[str, str]", snapshot[stats_key])
            profile = cast("dict[str, str]", snapshot[profile_key])
            valid_profile = profile.get("is_gm") != "1" and profile.get("user_id") == str(user)
            if (
                state.get("active") != "1"
                or float(state.get("next_at", 0)) > now
                or float(stats.get("work_last_at", 0)) < now - 5
                or int(stats.get("min_hp", 0)) <= 0
                or not valid_profile
            ):
                return Decision({"applied": False}, {})
            active = set(cast("set[str]", snapshot[SENTINEL_ACTIVE])) | {str(user)}
            return Decision(
                {"applied": True},
                {
                    SENTINEL_POLICY: {"next_at": str(now + SENTINEL_INTERVAL)},
                    SENTINEL_ACTIVE: active,
                    key: {
                        "code": code,
                        "until": str(now + SENTINEL_SECONDS),
                        "answered": "0",
                        "attempts": "0",
                        "at": str(now),
                    },
                },
            )

        await require_durable(redis)
        result = await transact(
            redis,
            (
                Resource(SENTINEL_POLICY, "hash"),
                Resource(SENTINEL_ACTIVE, "set"),
                Resource(stats_key, "hash"),
                Resource(profile_key, "hash"),
                Resource(key, "hash", ttl_seconds=600),
            ),
            operation_id(),
            {"sentinel": user, "at": now},
            decide,
        )
        await require_durable(redis)
        sender = self.deps.map_manager.get_player_message_sender(user)
        if result["applied"] and sender:
            await sender.send_console_msg(
                f"Centinela: responde /CENTINELA {code} en {SENTINEL_SECONDS} segundos "
                "para confirmar tu presencia."
            )

    async def _settle_challenge(self, user: int, enabled: bool) -> None:
        redis = self.deps.redis_client.redis
        key = f"security:sentinel:{user}"
        before = await redis.hgetall(key)
        if (
            before.get("answered") == "0"
            and enabled
            and float(before.get("until", 0)) > time.time()
        ):
            return
        failures, reports = "security:sentinel:failures", "chat:reports:denounce"
        identifier = operation_id()

        def decide(snapshot: Snapshot) -> Decision:
            state = cast("dict[str, str]", snapshot[key])
            if (
                enabled
                and state.get("answered") == "0"
                and float(state.get("until", 0)) > time.time()
            ):
                return Decision({"applied": False}, {})
            active = set(cast("set[str]", snapshot[SENTINEL_ACTIVE]))
            if str(user) not in active:
                return Decision({"applied": False}, {})
            active.discard(str(user))
            writes: dict[str, dict[str, str] | set[str]] = {SENTINEL_ACTIVE: active}
            missed = enabled and bool(state) and state.get("answered") == "0"
            if missed:
                counts = cast("dict[str, str]", snapshot[failures])
                writes.update(
                    {
                        failures: {str(user): str(int(counts.get(str(user), 0)) + 1)},
                        reports: {
                            identifier: json.dumps(
                                {
                                    "user": user,
                                    "at": int(time.time()),
                                    "text": (
                                        "No respondió al desafío del centinela; "
                                        "revisar evidencia antes de sancionar."
                                    ),
                                }
                            )
                        },
                    }
                )
            if state:
                writes[key] = {
                    "answered": "missed"
                    if missed
                    else state.get("answered", "canceled")
                    if enabled
                    else "canceled"
                }
            return Decision({"applied": True}, writes)

        await transact(
            redis,
            (
                Resource(key, "hash", keep_ttl=True),
                Resource(SENTINEL_ACTIVE, "set"),
                Resource(failures, "hash"),
                Resource(reports, "hash"),
            ),
            identifier,
            {"settle_sentinel": user},
            decide,
        )
        await require_durable(redis)
