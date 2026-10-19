"""Impuesto offline, transferencias y recuperación del ledger en Redis AOF propio."""

import asyncio
import json
from typing import TYPE_CHECKING
from unittest.mock import patch

from src.economy.tax_service import tax_status
from src.economy.tax_transactions import tax_key
from src.economy.taxes import TAX_POLICY_KEY, assess_tax
from src.operations.npc_commerce_smoke import settings
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.account_repository import AccountRepository
from src.security.session_lease import SessionLease
from src.services.account_moderation import AccountModeration
from src.services.bank_gold_transfer import transfer_gold
from src.utils.durability import require_durable
from src.utils.gold_atomic import change_gold, operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from typing import Any

    from src.config.game_config import RedisConfig

DAY = 20_000
USER = 1


async def scenario(
    config: RedisConfig, identities: tuple[str, str], *, seed: bool
) -> dict[str, Any]:
    """Repite las mismas operaciones identificadas antes y después de una caída.

    Returns:
        Saldos y recibos sintéticos con reloj controlado, sin datos reales.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        redis = client.redis
        stats = RedisKeys.player_user_stats(USER)
        if seed:
            await redis.hset(stats, mapping={"gold": "1000"})
            await redis.set(RedisKeys.bank_gold(USER), "2000")
            await redis.hset(
                TAX_POLICY_KEY,
                mapping={
                    "version": "1",
                    "enabled": "1",
                    "rate_bps": "100",
                    "activation_day": str(DAY - 1),
                },
            )
            await redis.hset(
                tax_key(USER),
                mapping={
                    "version": "1",
                    "last_day": str(DAY - 1),
                    "remainder": "0",
                    "total_paid": "0",
                },
            )
        with (
            patch("src.economy.taxes.utc_day", return_value=DAY),
            patch("src.economy.tax_service.utc_day", return_value=DAY),
        ):
            # El ingreso nuevo primero liquida el impuesto del día anterior.
            credit = await change_gold(redis, stats, 100, "credit", identity=identities[0])
            deposit = await transfer_gold(redis, USER, 100, "deposit", identities[1])
            status = await tax_status(redis, USER)
        expected = assess_tax(1000, 2000, DAY - 1, DAY)
        require(status["total_paid"] == expected.charged, "Un solo impuesto sobre el saldo previo")
        require(
            int(str(status["wallet"])) + int(str(status["bank"]))
            == expected.wallet + expected.bank + 100,
            "Ingreso nuevo no paga días anteriores",
        )
        await require_durable(redis)
        return {
            "credit": {"applied": credit.applied, "balance": credit.balance},
            "deposit": deposit,
            "status": status,
            "receipt": await redis.get(str(status["receipt"])),
        }
    finally:
        await client.disconnect()


async def moderation_scenario(config: RedisConfig, identity: str, *, seed: bool) -> dict[str, Any]:
    """Exige que un bloqueo y su auditoría sobrevivan al mismo SIGKILL del ensayo.

    Returns:
        Estado sintético e identidad estable del único registro auditado.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        repo = AccountRepository(client)
        if seed:
            await client.redis.set(RedisKeys.ACCOUNTS_COUNTER, "1000")
            await repo.create_account("OperatorFixture", "synthetic-hash", "test@example.invalid")
            await repo.create_account("BlockedFixture", "synthetic-hash", "test@example.invalid")
            await repo.set_gm_status("OperatorFixture", is_gm=True)
        actor_fields = await repo.get_account("OperatorFixture") or {}
        target_fields = await repo.get_account("BlockedFixture") or {}
        actor = int(actor_fields.get("user_id", "0"))
        target = int(target_fields.get("user_id", "0"))
        result = await AccountModeration(repo).apply(
            actor,
            "BlockedFixture",
            active=True,
            days=0,
            reason="Ensayo AOF propio",
            identity=identity,
        )
        require(result["applied"], "Bloqueo confirmado")
        require(
            not await SessionLease(client.redis, target).acquire(),
            "Bloqueo antes de entrar al mundo",
        )
        audit = [key async for key in client.redis.scan_iter(match="moderation:audit:*")]
        require(len(audit) == 1, "Un solo registro auditado tras reintentos")
        return {"result": result, "audit": await client.redis.get(audit[0]), "target": target}
    finally:
        await client.disconnect()


def main() -> None:
    """Verifica fsync y reintentos sin abrir Redis del operador."""
    identities = operation_id(), operation_id()
    moderation_id = operation_id()
    with RedisSandbox() as sandbox:
        before = asyncio.run(scenario(settings(sandbox), identities, seed=True))
        ban_before = asyncio.run(moderation_scenario(settings(sandbox), moderation_id, seed=True))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        after = asyncio.run(scenario(settings(sandbox), identities, seed=False))
        ban_after = asyncio.run(moderation_scenario(settings(sandbox), moderation_id, seed=False))
        require(before == after, "Ledger y recibos íntegros tras SIGKILL sin doble cobro")
        require(ban_before == ban_after, "Bloqueo permanente y auditoría íntegros tras SIGKILL")
    print(
        json.dumps(
            {
                "daily_tax_one_percent_offline": True,
                "credit_not_retroactive": True,
                "wallet_and_bank": True,
                "aof_recovery": True,
                "identified_retries_once": True,
                "moderation_aof_recovery": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
