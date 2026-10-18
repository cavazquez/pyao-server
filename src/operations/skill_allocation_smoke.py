"""Presupuesto y replay de habilidades después de SIGKILL de Redis AOF propio."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig
from src.models.skills import CATALOG
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.operations.trade_atomic_smoke import settings
from src.repositories.player_repository import PlayerRepository
from src.services.skill_allocation import allocate_skill_points
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

INITIAL_POINTS = 8
REMAINING_POINTS = 3
EXPECTED_MAGIC = 15
EXPECTED_WOODCUTTING = 10
EXPECTED_XP = 90


def deltas() -> tuple[tuple[int, int], ...]:
    """Congela los 22 IDs y una asignación de cinco puntos a magia.

    Returns:
        Pares canónicos; las habilidades pendientes no reciben puntos.
    """
    return tuple((entry.skill_id, 5 if entry.skill_id == 1 else 0) for entry in CATALOG)


async def verify(player: PlayerRepository) -> None:
    """Comprueba el presupuesto y que XP y otros niveles permanecieron intactos."""
    require(await player.get_skill_points(1) == REMAINING_POINTS, "Un solo gasto de cinco puntos")
    skills = await player.get_skills(1)
    require(skills is not None and skills["magia"] == EXPECTED_MAGIC, "Nivel confirmado")
    require(skills is not None and skills["talar"] == EXPECTED_WOODCUTTING, "Otro nivel conservado")
    require(
        await player.redis.hget(RedisKeys.player_skills(1), "xp:talar") == str(EXPECTED_XP),
        "XP no convertida en nivel ni gastada",
    )


async def exercise(
    config: RedisConfig, identities: tuple[str, str], *, recovery: bool = False
) -> None:
    """Usa exclusivamente recursos sintéticos del contenedor de este ensayo."""
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        if not recovery:
            await client.hset(
                RedisKeys.player_skills(1),
                mapping={
                    "points": str(INITIAL_POINTS),
                    "level:magia": "10",
                    "level:talar": str(EXPECTED_WOODCUTTING),
                    "xp:talar": str(EXPECTED_XP),
                    "xp_per_level": "100",
                },
            )
        results = await asyncio.gather(
            *(allocate_skill_points(client.redis, 1, identity, deltas()) for identity in identities)
        )
        require(
            sum(bool(result["applied"]) for result in results) == 1, "Dos pedidos no sobregiran"
        )
        await verify(PlayerRepository(client))
        for identity, result in zip(identities, results, strict=True):
            require(
                await allocate_skill_points(client.redis, 1, identity, deltas()) == result,
                "Replay devuelve el resultado original",
            )
        await verify(PlayerRepository(client))
        await require_durable(client.redis)
    finally:
        await client.disconnect()


def main() -> None:
    """Mata y reinicia sólo el Redis y volumen creados por esta instancia."""
    identities = operation_id(), operation_id()
    with RedisSandbox() as sandbox:
        asyncio.run(asyncio.wait_for(exercise(settings(sandbox), identities), timeout=45))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        asyncio.run(
            asyncio.wait_for(exercise(settings(sandbox), identities, recovery=True), timeout=30)
        )
    print(
        json.dumps(
            {
                "budget_atomic": True,
                "concurrent_requests_no_overspend": True,
                "xp_preserved": True,
                "sigkill_replay_once": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
