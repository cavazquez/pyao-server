"""Aprendizaje de pergaminos conservado después de SIGKILL del Redis aislado."""

import asyncio
import json

from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.operations.trade_atomic_smoke import settings
from src.repositories.account_repository import AccountRepository
from src.repositories.spellbook_repository import SpellbookRepository
from src.services.scroll_learning import ScrollRule, learn_scroll
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys


async def exercise(sandbox: RedisSandbox, identity: str, *, recovery: bool = False) -> None:
    """Comprueba que libro e inventario sobreviven juntos y el replay no consume otra unidad."""
    client = RedisClient()
    await client.connect(settings(sandbox), seed_defaults=False)
    try:
        if not recovery:
            require(
                await AccountRepository(client).create_account(
                    "usr", "unused-fixture-hash", "usr@example.invalid", {"job": 1}
                )
                == 1,
                "Cuenta creada por el repositorio real",
            )
            await client.hset(RedisKeys.player_inventory(1), mapping={"slot_30": "197:2"})
            await client.hset(
                RedisKeys.player_user_stats(1), mapping={"min_hp": "100", "level": "5"}
            )
            await client.hset(RedisKeys.player_skills(1), mapping={"level:magia": "20"})
        result = await learn_scroll(
            client.redis, 1, "usr", 30, identity, ScrollRule(197, 6, 1, 12, (1,))
        )
        require(result["applied"] is True, "Hechizo aprendido")
        require(await SpellbookRepository(client).get_all_spells(1) == {1: 6}, "Libro conservado")
        require(
            await client.hget(RedisKeys.player_inventory(1), "slot_30") == "197:1",
            "Una sola unidad consumida",
        )
    finally:
        await client.disconnect()


def main() -> None:
    """Usa exclusivamente el contenedor y volumen descartables creados por este ensayo."""
    identity = operation_id()
    with RedisSandbox() as sandbox:
        asyncio.run(asyncio.wait_for(exercise(sandbox, identity), timeout=30))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        asyncio.run(asyncio.wait_for(exercise(sandbox, identity, recovery=True), timeout=30))
    print(
        json.dumps(
            {"learn_atomic": True, "sigkill_replay_once": True, "production_data_used": False}
        )
    )


if __name__ == "__main__":
    main()
