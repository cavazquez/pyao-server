"""Compra concurrente y venta impar en Redis nativo con replay tras SIGKILL."""

import asyncio
import json
from typing import TYPE_CHECKING

from src.config.game_config import RedisConfig
from src.models.item import Item, ItemType
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.merchant_repository import MerchantRepository
from src.repositories.player_repository import PlayerRepository
from src.services.commerce_service import CommerceService
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from typing import Any

NPC_ID = 123
PRICE = 11
STARTING_GOLD = 100
EXPECTED_TOTAL_GOLD = 204  # Dos saldos iniciales - compra 11 + venta 15.
EXPECTED_ITEMS = 16  # Diez ganancias concurrentes además de las seis unidades iniciales.
LAST_SLOT = 30


def settings(sandbox: RedisSandbox) -> RedisConfig:
    """Devuelve configuración únicamente del Redis descartable propio.

    Returns:
        Endpoint autenticado del ensayo, sin datos productivos.
    """
    return RedisConfig(host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file)


async def scenario(
    config: RedisConfig, identities: tuple[str, str, str], *, seed: bool
) -> dict[str, Any]:
    """Ejecuta acciones identificadas y devuelve una instantánea para comparar tras la caída.

    Returns:
        Recursos y resultados sintéticos, sin credenciales ni rutas de secretos.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        inventory, player = InventoryRepository(client), PlayerRepository(client)
        merchant = MerchantRepository(client)
        catalog = {
            1: Item(
                item_id=1,
                name="Poción",
                item_type=ItemType.POTION,
                graphic_id=100,
                value=PRICE,
                stackable=True,
            )
        }
        service = CommerceService(inventory, merchant, catalog, player)
        if seed:
            for user_id in [1, 2]:
                await player.update_gold(user_id, STARTING_GOLD)
            await inventory.set_slot(1, LAST_SLOT, 1, 5)
            await client.hset(RedisKeys.merchant_inventory(NPC_ID), mapping={"slot_1": "1:1"})
        purchases = asyncio.gather(
            *(
                service.buy_item(user_id, NPC_ID, 1, 1, operation_id=identities[user_id - 1])
                for user_id in [1, 2]
            )
        )
        if seed:
            await asyncio.gather(
                purchases,
                *(inventory.add_item(1, 1, 1) for _ in range(10)),
                inventory.swap_slots(1, 30, 1),
                inventory.swap_slots(1, 1, 30),
            )
        results = await purchases
        require(
            sum(success for success, _message in results) == 1, "Una compra por la última unidad"
        )
        success, message = await service.sell_item(
            1, NPC_ID, LAST_SLOT, 3, operation_id=identities[2]
        )
        require(success and "15 oro" in message, "Venta con fórmula impar exacta")
        balances = [await player.get_gold(user_id) for user_id in [1, 2]]
        require(sum(balances) == EXPECTED_TOTAL_GOLD, "Sin doble débito ni pago repetido")
        inventories = await asyncio.gather(
            *(inventory.get_inventory_slots(user_id) for user_id in [1, 2])
        )
        stock = await merchant.get_all_items(NPC_ID)
        total_items = sum(stack.quantity for values in inventories for stack in values.values())
        require(
            total_items + sum(item.quantity for item in stock) == EXPECTED_ITEMS,
            "Objetos conservados",
        )
        return {
            "balances": balances,
            "inventories": [await inventory.get_inventory(user_id) for user_id in [1, 2]],
            "stock": await merchant.get_inventory(NPC_ID),
            "results": results,
        }
    finally:
        await client.disconnect()


def main() -> None:
    """Reinicia únicamente su Redis propio y compara todos los recursos después del replay."""
    identities = operation_id(), operation_id(), operation_id()
    with RedisSandbox() as sandbox:
        before = asyncio.run(
            asyncio.wait_for(scenario(settings(sandbox), identities, seed=True), 60)
        )
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        after = asyncio.run(
            asyncio.wait_for(scenario(settings(sandbox), identities, seed=False), 45)
        )
        require(
            after == before, "Reintentos tras caída conservan exactamente stock, oro e inventarios"
        )
    print(
        json.dumps(
            {
                "last_unit_race": True,
                "odd_sale_price": True,
                "atomic_stock_gold_inventory": True,
                "sigkill_recovery": True,
                "identified_retry_once": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
