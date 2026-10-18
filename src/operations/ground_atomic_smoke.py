"""Drop y pickup persistidos en Redis nativo, competencia y recuperación tras SIGKILL."""

import asyncio
import json
from typing import TYPE_CHECKING

from src.config.game_config import RedisConfig
from src.game.map_manager import MapManager
from src.models.item_constants import MAX_PLAYER_GOLD
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.ground_items_repository import GroundItemsRepository
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import stack_identity
from src.utils.redis_client import RedisClient

if TYPE_CHECKING:
    from typing import Any


MAP_ID = 1
POSITION = 50
LAST_SLOT = 30
EXPECTED_ITEMS = 5
EXPECTED_FIRST_GOLD = 90


def settings(sandbox: RedisSandbox) -> RedisConfig:
    """Resuelve sólo el endpoint autenticado propio.

    Returns:
        Configuración del Redis descartable.
    """
    return RedisConfig(host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file)


async def apply(
    manager: MapManager, client: RedisClient, request: GroundRequest, identity: str
) -> dict[str, Any]:
    """Ejecuta commit y recarga de la vista con la misma ruta que los handlers.

    Returns:
        Resultado confirmado de la transferencia.
    """
    return await manager.apply_ground_operation(
        request.map_id,
        request.x,
        request.y,
        client.redis,
        lambda: transfer_ground(client.redis, request, identity),
        operation_id=identity,
    )


async def scenario(
    config: RedisConfig, identities: tuple[str, ...], *, seed: bool
) -> dict[str, Any]:
    """Conserva peticiones e IDs para repetirlos después de la caída.

    Returns:
        Recursos y resultados sintéticos para comparación exacta.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        player, inventory = PlayerRepository(client), InventoryRepository(client)
        ground = GroundItemsRepository(client)
        manager = MapManager(ground)
        if seed:
            for user_id in [1, 2]:
                await player.set_position(user_id, POSITION, POSITION, MAP_ID)
                gold = 100 if user_id == 1 else MAX_PLAYER_GOLD - 10
                await player.set_stats(user_id, 100, 100, 100, 100, 100, 100, gold, 1, 300, 0)
            await inventory.set_slot(1, LAST_SLOT, 1, EXPECTED_ITEMS)
        item_drop = GroundRequest(
            1,
            MAP_ID,
            POSITION,
            POSITION,
            "drop_item",
            slot=LAST_SLOT,
            quantity=3,
            expected_item_id=1,
        )
        dropped = await apply(manager, client, item_drop, identities[0])
        require(dropped["applied"], "Drop identificado y debitado")
        requests = [
            GroundRequest(
                user_id,
                MAP_ID,
                POSITION,
                POSITION,
                "pickup",
                expected_stack=stack_identity(identities[0]),
            )
            for user_id in [1, 2]
        ]
        # Llamadas directas simultáneas prueban también WATCH frente a otro proceso/índice.
        picked = await asyncio.gather(
            *(
                transfer_ground(client.redis, request, identities[index + 1])
                for index, request in enumerate(requests)
            )
        )
        require(sum(result["applied"] for result in picked) == 1, "Una acreditación por stack")
        gold_drop = GroundRequest(1, MAP_ID, POSITION, POSITION, "drop_gold", quantity=40)
        require((await apply(manager, client, gold_drop, identities[3]))["applied"], "Drop oro")
        for user_id, identity in [(2, identities[4]), (1, identities[5])]:
            request = GroundRequest(
                user_id,
                MAP_ID,
                POSITION,
                POSITION,
                "pickup",
                expected_stack=stack_identity(identities[3]),
            )
            require(
                (await apply(manager, client, request, identity))["applied"], "Pickup oro o replay"
            )
        require(
            await player.get_gold(1) == EXPECTED_FIRST_GOLD, "Remanente conservado y recuperado"
        )
        require(await player.get_gold(2) == MAX_PLAYER_GOLD, "Tope exacto sin descartar remanente")
        inventories = await asyncio.gather(
            *(inventory.get_inventory_slots(user_id) for user_id in [1, 2])
        )
        require(
            sum(item.quantity for values in inventories for item in values.values())
            == EXPECTED_ITEMS,
            "Unidades conservadas entre jugadores",
        )
        require(
            await ground.load_ground_items(MAP_ID) == {}, "Suelo vacío después de recuperar todo"
        )
        require(
            manager.get_ground_items(MAP_ID, POSITION, POSITION) == [],
            "Caché actual después de replay",
        )
        return {
            "inventories": [await inventory.get_inventory(user_id) for user_id in [1, 2]],
            "balances": [await player.get_gold(user_id) for user_id in [1, 2]],
            "picked": picked,
        }
    finally:
        await client.disconnect()


def main() -> None:
    """Compara todos los recursos antes y después de matar sólo su Redis propio."""
    identities = tuple(operation_id() for _ in range(6))
    with RedisSandbox() as sandbox:
        before = asyncio.run(
            asyncio.wait_for(scenario(settings(sandbox), identities, seed=True), 90)
        )
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():
            pass
        after = asyncio.run(
            asyncio.wait_for(scenario(settings(sandbox), identities, seed=False), 90)
        )
        require(before == after, "Replay de drop/pickup tras caída sin duplicación ni pérdida")
    print(
        json.dumps(
            {
                "atomic_ground_inventory_gold": True,
                "two_players_one_stack": True,
                "gold_remainder": True,
                "slot_30": True,
                "sigkill_recovery": True,
                "identified_retries_once": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
