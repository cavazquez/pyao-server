"""Prueba de concurrencia de oro contra Redis real nuevo y autenticado."""

import asyncio
import json

from src.config.game_config import RedisConfig
from src.models.item_constants import MAX_PLAYER_GOLD
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox
from src.repositories.player_repository import PlayerRepository
from src.services.bank_gold_transfer import transfer_gold
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

PARALLEL_CREDITS = 100
COMPETING_DEBIT = 80


async def scenario(settings: RedisConfig) -> dict[str, bool]:
    """Demuestra saldo exacto, débito condicional y reintento sobre Redis nativo.

    Returns:
        Evidencia sin datos ni nombres de cuentas reales.
    """
    client = RedisClient()
    await client.connect(settings, seed_defaults=False)
    try:
        repo = PlayerRepository(client)
        await repo.update_gold(1, 0)
        await asyncio.gather(*(repo.add_gold(1, 1) for _ in range(PARALLEL_CREDITS)))
        require(await repo.get_gold(1) == PARALLEL_CREDITS, "Créditos concurrentes sin pérdida")
        debits = await asyncio.gather(
            repo.remove_gold(1, COMPETING_DEBIT), repo.remove_gold(1, COMPETING_DEBIT)
        )
        require(sorted(debits) == [False, True], "Un único débito con saldo suficiente")
        identity = operation_id()
        await repo.add_gold(1, 3, operation_id=identity)
        await repo.add_gold(1, 3, operation_id=identity)
        require(await repo.get_gold(1) == PARALLEL_CREDITS - COMPETING_DEBIT + 3, "Replay único")
        await repo.update_gold(1, MAX_PLAYER_GOLD - 1)
        accepted, balance = await repo.add_gold_capped(1, 9)
        require((accepted, balance) == (1, MAX_PLAYER_GOLD), "Cap sin overflow")
        await repo.update_gold(2, 100)
        transfers = await asyncio.gather(
            *(transfer_gold(client.redis, 2, 80, "deposit", operation_id()) for _ in range(2))
        )
        require(sum(t["applied"] for t in transfers) == 1, "Depósitos sin sobregiro")
        require(await repo.get_gold(2) == PARALLEL_CREDITS - COMPETING_DEBIT, "Saldo jugador")
        require(await client.get(RedisKeys.bank_gold(2)) == str(COMPETING_DEBIT), "Saldo banco")
        identity = operation_id()
        result = await transfer_gold(client.redis, 2, 10, "withdraw", identity)
        require(
            await transfer_gold(client.redis, 2, 10, "withdraw", identity) == result, "Replay banco"
        )
        require(
            await repo.get_gold(2) + int(await client.get(RedisKeys.bank_gold(2)) or 0)
            == PARALLEL_CREDITS,
            "Conservación total",
        )
        return {
            "concurrent_credits": True,
            "conditional_debits": True,
            "identified_retry": True,
            "bounded_credit": True,
            "atomic_bank_transfer": True,
            "bank_identified_retry": True,
            "production_data_used": False,
        }
    finally:
        await client.disconnect()


def main() -> None:
    """Ejecuta la prueba aislada y elimina únicamente su contenedor y volumen."""
    with RedisSandbox() as sandbox:
        settings = RedisConfig(
            host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file
        )
        result = asyncio.run(asyncio.wait_for(scenario(settings), timeout=45))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
