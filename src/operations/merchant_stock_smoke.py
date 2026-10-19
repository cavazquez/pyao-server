"""Stock real en AOF: compras concurrentes, reventa y reinicio abrupto."""

import asyncio
import json
from typing import TYPE_CHECKING

from src.economy.merchant_stock import StockEntry, catalog_key, restock_merchant, seed_merchant
from src.operations.npc_commerce_smoke import NPC_ID, scenario, settings
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig


async def reload_catalog(config: RedisConfig, *, seed: bool) -> dict[str, object]:
    """Carga un seed diferente comprobando que el inventario confirmado prevalece.

    Returns:
        Stock, índice y política durables de un mercader sintético.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        redis = client.redis
        if seed:
            await redis.hset(RedisKeys.merchant_inventory(NPC_ID), "slot_20", "139:3")
        await seed_merchant(redis, NPC_ID, (StockEntry(1, 1000 if seed else 2000, 100),))
        before = await redis.hgetall(RedisKeys.merchant_inventory(NPC_ID))
        policy = await redis.hgetall(catalog_key(NPC_ID))
        await seed_merchant(redis, NPC_ID, (StockEntry(1, 3000, 300),))
        require(
            before == await redis.hgetall(RedisKeys.merchant_inventory(NPC_ID)),
            "Reload sin reposición",
        )
        require(policy == await redis.hgetall(catalog_key(NPC_ID)), "Política desde Redis")
        require(before["slot_20"] == "139:3", "Reventa fuera del catálogo conservada")
        # Ningún intervalo ha vencido: repetir el worker no modifica el stock.
        require(
            await restock_merchant(redis, NPC_ID, now=int(policy["last_restock"])) == 0,
            "Corte idempotente",
        )
        await require_durable(redis)
        return {
            "stock": before,
            "policy": policy,
            "index": sorted(await redis.smembers(f"merchant:{NPC_ID}:items")),
        }
    finally:
        await client.disconnect()


def main() -> None:
    """Mata y recupera únicamente el Redis creado por este ensayo."""
    identities = operation_id(), operation_id(), operation_id()
    with RedisSandbox() as sandbox:
        config = settings(sandbox)
        asyncio.run(scenario(config, identities, seed=True))
        before = asyncio.run(reload_catalog(config, seed=True))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        after = asyncio.run(reload_catalog(settings(sandbox), seed=False))
        require(before == after, "Stock e índices recuperados desde AOF")
    print(
        json.dumps(
            {
                "redis_authoritative": True,
                "last_unit_race": True,
                "player_resale_preserved": True,
                "catalog_reload_preserved": True,
                "aof_sigkill_recovery": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
