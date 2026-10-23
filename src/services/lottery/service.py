"""Vista pública acotada y confirmaciones de apuestas ante el NPC seleccionado."""

import json
from typing import TYPE_CHECKING, Any

from src.services.lottery.repository import LotteryRepository, nearby
from src.services.lottery.rules import (
    LAST_WINNER,
    MAX_POOL,
    MIN_BET,
    NPC_INSTANCE,
    participants_key,
    round_key,
)
from src.utils.durability import require_durable
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer


class LotteryService:
    """Consulta remota pública; participar exige seleccionar físicamente al lotero."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Conserva sólo infraestructura y la versión durable ya publicada."""
        from src.config.config_manager import config_manager  # ruff: ignore[import-outside-top-level]

        self.repo = LotteryRepository(
            deps.redis_client.redis,
            seconds=int(str(config_manager.get("game.lottery.round_seconds", 300))),
        )
        self.last_durable = ""

    async def snapshot(self, user: int) -> dict[str, Any]:
        """Lee una vista consistente sin exponer la semilla secreta ni participantes.

        Returns:
            Pozo, aporte propio, reglas, reloj y ganador histórico.
        """
        redis = self.repo.redis
        identity = await self.repo.current()
        async with redis.pipeline(transaction=True) as pipe:
            pipe.hgetall(round_key(identity))
            pipe.hget(participants_key(identity), str(user))
            pipe.get(LAST_WINNER)
            pipe.hgetall(RedisKeys.player_user_stats(user))
            pipe.hgetall(RedisKeys.player_position(user))
            pipe.hgetall(RedisKeys.npc_instance(NPC_INSTANCE))
            pipe.hgetall(f"chat:target:{user}")
            state, entry, last, stats, position, npc, target = await pipe.execute()
        if last and last != self.last_durable:
            await require_durable(redis)
            self.last_durable = last
        row = json.loads(entry) if entry else {"gross": 0, "fee": 0, "net": 0}
        last_winner = json.loads(last) if last else {}
        # Ni el reloj ni el porcentaje del cliente se usan para cobrar.
        now = int(self.repo.clock())
        deadline = int(state.get("closes_at", 0))
        return {
            "round": identity,
            "status": state.get("status", "open"),
            "pool": int(state.get("pool", 0)),
            "fees": int(state.get("fees", 0)),
            "gross": row["gross"],
            "fee": row["fee"],
            "net": row["net"],
            "participants": int(state.get("count", 0)),
            "minimum": MIN_BET,
            "maximum": MAX_POOL,
            "closes_at": deadline,
            "server_time": now,
            "round_seconds": int(state.get("seconds", self.repo.seconds)),
            "can_bet": nearby(stats, position, npc, target)
            and state.get("status") == "open"
            and (not deadline or now < deadline),
            "npc": NPC_INSTANCE,
            "commitment": state.get("commitment", ""),
            "devalued": int(state.get("devalued", 0)),
            "last_winner": last_winner,
            "claim_pending": state.get("status") == "pending"
            and int(state.get("winner", 0)) == user,
        }

    async def bet(self, user: int, request: dict[str, Any]) -> dict[str, Any]:
        """Entrega al repositorio la identidad original del reintento.

        Returns:
            Comprobante económico durable; la revisión efímera no invalida reintentos.
        """
        params = request["params"]
        await self.repo.refresh(params["round"])
        return await self.repo.bet(
            user, request["id"], params["round"], params["npc"], params["gross"]
        )
