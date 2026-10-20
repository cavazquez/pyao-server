"""Bootstrap real sobre Redis descartable: vacío, parcial y recuperación desde AOF."""

import asyncio
import json
from typing import TYPE_CHECKING

from src.config.config_manager import config_manager
from src.core.redis_initializer import RedisInitializer
from src.core.schema_manager import CURRENT_SCHEMA_VERSION, SCHEMA_KEY
from src.models.crafting_data_loader import CRAFTING_KEY
from src.models.skill_data_loader import SKILL_RULES_KEY
from src.operations.npc_commerce_smoke import settings
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.operations.two_client_smoke import scenario as clients_scenario
from src.utils.durability import require_durable

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig
    from src.utils.redis_client import RedisClient

PRESERVED_HASHES = (
    "world:home:1",
    "player:812:user_stats",
    "player:812:inventory",
    "player:812:equipment",
    "player:812:bank_inventory",
    "merchant:7:inventory",
    "merchant:7:catalog",
)
PRESERVED_STRINGS = (CRAFTING_KEY, SKILL_RULES_KEY, "server:motd", "server:dice:min_value")
TTL_SECONDS = 3600
TTL_TOLERANCE_SECONDS = 100


async def snapshot(client: RedisClient) -> dict[str, object]:
    """Lee estado durable que los cargadores no pueden reemplazar.

    Returns:
        Recursos de prueba sin credenciales.
    """
    redis = client.redis
    return {
        "hashes": {key: await redis.hgetall(key) for key in PRESERVED_HASHES},
        "strings": {key: await redis.get(key) for key in PRESERVED_STRINGS},
    }


async def bootstrap(config: RedisConfig, *, seed: bool) -> dict[str, object]:
    """Ejecuta el inicializador de producción y valida el snapshot antes/después.

    Returns:
        Estado que debe sobrevivir al arranque parcial y al reinicio de Redis.
    """
    config_manager.set("redis.host", config.host)
    config_manager.set("redis.port", config.port)
    config_manager.set("redis.password_file", str(config.password_file))
    client = await RedisInitializer.initialize()
    try:
        redis = client.redis
        require(
            await redis.hget(SCHEMA_KEY, "version") == str(CURRENT_SCHEMA_VERSION),
            "Esquema inicializado sin semillas manuales",
        )
        if seed:
            await redis.set(CRAFTING_KEY, "[]")
            await redis.set("server:motd", "")
            await redis.set("server:dice:min_value", "0")
            await redis.expire(SKILL_RULES_KEY, TTL_SECONDS)
            await redis.hset("world:home:1", mapping={"map": "34", "x": "0"})
            await redis.hset("player:812:user_stats", mapping={"gold": "0", "bank_gold": "42"})
            await redis.hset("player:812:inventory", "slot_30", "15:2")
            await redis.hset("player:812:equipment", "weapon", "15")
            await redis.hset("player:812:bank_inventory", "slot_1", "38:3")
            await redis.hset("merchant:7:inventory", mapping={"slot_1": "", "slot_20": "139:3"})
        before = await snapshot(client)
        await redis.delete("world:home:6", "server:dice:max_value")
        await RedisInitializer.initialize()
        require(await snapshot(client) == before, "Bootstrap parcial conserva estado y stock")
        require(await redis.hget("world:home:6", "map") == "151", "Completa la ciudad ausente")
        require(await redis.get("server:dice:max_value") == "18", "Completa el default ausente")
        require(
            TTL_SECONDS - TTL_TOLERANCE_SECONDS <= await redis.ttl(SKILL_RULES_KEY) <= TTL_SECONDS,
            "Conserva TTL existente",
        )
        await require_durable(redis)
        return before
    finally:
        await client.disconnect()


def main() -> None:
    """No accede a ningún Redis del operador: crea y destruye su sandbox propio."""
    with RedisSandbox() as sandbox:
        config = settings(sandbox)
        before = asyncio.run(bootstrap(config, seed=True))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        after = asyncio.run(bootstrap(settings(sandbox), seed=False))
        require(before == after, "Estado durable conservado tras SIGKILL y bootstrap")
        clients = asyncio.run(clients_scenario(settings(sandbox)))
    print(
        json.dumps(
            {
                "empty_bootstrap": True,
                "partial_bootstrap": True,
                "custom_configuration_preserved": True,
                "depleted_stock_preserved": True,
                "ttl_preserved": True,
                "aof_sigkill_recovery": True,
                "two_client_logins_and_movement": clients,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
