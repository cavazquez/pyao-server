"""Banco/inventario en Redis nativo, persistencia y replay después de SIGKILL."""

import asyncio
import json
from typing import Literal

from src.config.game_config import RedisConfig
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.bank_repository import BankRepository
from src.repositories.inventory_repository import InventoryRepository
from src.services.bank_item_transfer import transfer_bank_item
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

ITEM_ID = 1
SOURCE_QUANTITY = 45
INITIAL_BANK_QUANTITY = 32760
DEPOSIT_QUANTITY = 42
WITHDRAW_QUANTITY = 27
LAST_SLOT = 30
BANK_REMAINDER = 8


def settings(sandbox: RedisSandbox) -> RedisConfig:
    """Devuelve únicamente el endpoint descartable propio.

    Returns:
        Configuración autenticada y local del ensayo.
    """
    return RedisConfig(host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file)


async def scenario(config: RedisConfig, deposit_id: str, withdraw_id: str, *, seed: bool) -> None:
    """Distribuye stacks o comprueba su recuperación tras una caída."""
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        inventory = InventoryRepository(client)
        if seed:
            await inventory.set_slot(1, LAST_SLOT, ITEM_ID, SOURCE_QUANTITY)
            await client.hset(
                RedisKeys.bank(1), mapping={"slot_1": f"{ITEM_ID}:{INITIAL_BANK_QUANTITY}"}
            )
        operations: tuple[tuple[str, int, int, Literal["deposit", "withdraw"]], ...] = (
            (deposit_id, LAST_SLOT, DEPOSIT_QUANTITY, "deposit"),
            (withdraw_id, 2, WITHDRAW_QUANTITY, "withdraw"),
        )
        for identity, slot, quantity, direction in operations:
            result = await transfer_bank_item(client.redis, 1, slot, quantity, direction, identity)
            require(result["applied"], "Transferencia confirmada o replay después del reinicio")
        require(await inventory.get_slot(1, LAST_SLOT) == (ITEM_ID, 20), "Slot 30 recuperado")
        require(await inventory.get_slot(1, 1) == (ITEM_ID, 10), "Segundo stack recuperado")
        bank = BankRepository(client)
        item = await bank.get_item(1, 2)
        require(item is not None and item.quantity == BANK_REMAINDER, "Remanente banco recuperado")
        bank_total = sum(item.quantity for item in await bank.get_all_items(1))
        inventory_total = sum(
            item.quantity for item in (await inventory.get_inventory_slots(1)).values()
        )
        require(
            bank_total + inventory_total == INITIAL_BANK_QUANTITY + SOURCE_QUANTITY,
            "Total conservado",
        )
    finally:
        await client.disconnect()


def main() -> None:
    """Comprueba dos contenedores y sus recibos sin tocar Redis de usuarios."""
    deposit_id, withdraw_id = operation_id(), operation_id()
    with RedisSandbox() as sandbox:
        asyncio.run(
            asyncio.wait_for(scenario(settings(sandbox), deposit_id, withdraw_id, seed=True), 45)
        )
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        asyncio.run(
            asyncio.wait_for(scenario(settings(sandbox), deposit_id, withdraw_id, seed=False), 30)
        )
    print(
        json.dumps(
            {
                "atomic_bank_inventory": True,
                "stacks_distributed": True,
                "slot_30": True,
                "sigkill_recovery": True,
                "identified_retry_once": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
