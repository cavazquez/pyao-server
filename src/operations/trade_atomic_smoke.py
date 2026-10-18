"""Intercambio conjunto en Redis nativo y recuperación después de SIGKILL."""

import asyncio
import json

from redis.exceptions import RedisError

from src.config.game_config import RedisConfig
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.player_repository import PlayerRepository
from src.services.trade_settlement import (
    OfferedItem,
    ParticipantOffer,
    get_trade_result,
    settle_trade,
)
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient

CAPACITY = 30
MAX_STACK = 20
A_INITIAL_BALANCE = 100
A_BALANCE = 140
B_BALANCE = 160


def offers() -> tuple[ParticipantOffer, ParticipantOffer]:
    """Congela dos ofertas de cuentas sintéticas.

    Returns:
        Participantes, oro e items usados durante todo el ensayo y su recuperación.
    """
    return (
        ParticipantOffer(1, 20, (OfferedItem(1, 101, 2),)),
        ParticipantOffer(2, 60, (OfferedItem(2, 202, 1),)),
    )


def settings(sandbox: RedisSandbox) -> RedisConfig:
    """Utiliza únicamente el endpoint y secreto del contenedor propio.

    Returns:
        Configuración autenticada del Redis descartable.
    """
    return RedisConfig(host="127.0.0.1", port=sandbox.port, password_file=sandbox.password_file)


async def prepare(config: RedisConfig, identity: str, *, enabled: bool = True) -> None:
    """Prueba confirmaciones concurrentes o rechazo previo sin AOF.

    Raises:
        RuntimeError: Si un Redis sin AOF acepta una liquidación.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        player, inventory = PlayerRepository(client), InventoryRepository(client)
        await player.update_gold(1, A_INITIAL_BALANCE)
        await player.update_gold(2, 200)
        await inventory.set_slot(1, 1, 101, 5)
        await inventory.set_slot(2, 2, 202, 3)
        if not enabled:
            try:
                await settle_trade(client.redis, identity, offers(), CAPACITY, MAX_STACK)
            except RedisError, RuntimeError:
                require(
                    await player.get_gold(1) == A_INITIAL_BALANCE,
                    "Rechazo previo sin modificar oro",
                )
                require(
                    await inventory.get_slot(1, 1) == (101, 5), "Rechazo previo sin retirar items"
                )
                require(
                    not await client.redis.exists(f"trade:settlement:{identity}"), "Sin journal"
                )
                return
            msg = "Redis sin AOF no debe aceptar un intercambio durable"
            raise RuntimeError(msg)
        results = await asyncio.gather(
            *(settle_trade(client.redis, identity, offers(), CAPACITY, MAX_STACK) for _ in range(3))
        )
        require(
            all(result["applied"] for result in results), "Un mismo commit para tres confirmaciones"
        )
        await verify_resources(player, inventory)
    finally:
        await client.disconnect()


async def verify_resources(player: PlayerRepository, inventory: InventoryRepository) -> None:
    """Comprueba todos los recursos de la liquidación, antes y después del reinicio."""
    require(await player.get_gold(1) == A_BALANCE, "Saldo A")
    require(await player.get_gold(2) == B_BALANCE, "Saldo B")
    require(await inventory.get_slot(1, 1) == (101, 3), "Items retirados A")
    require(await inventory.get_slot(1, 2) == (202, 1), "Items recibidos A")
    require(await inventory.get_slot(2, 1) == (101, 2), "Items recibidos B")
    require(await inventory.get_slot(2, 2) == (202, 2), "Items retirados B")


async def recover(config: RedisConfig, identity: str) -> None:
    """Consulta el journal y reintenta después de una caída sin recibo temporal."""
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        result = await get_trade_result(client.redis, identity, 1)
        require(result is not None and result["applied"], "Journal durable tras SIGKILL")
        await client.delete(f"operation:resources:{identity}")
        require(
            await settle_trade(client.redis, identity, offers(), CAPACITY, MAX_STACK) == result,
            "Replay resuelto desde journal sin duplicar",
        )
        await verify_resources(PlayerRepository(client), InventoryRepository(client))
    finally:
        await client.disconnect()


def main() -> None:
    """Elimina únicamente contenedores/volúmenes propios y emite evidencia sin datos reales."""
    identity = operation_id()
    with RedisSandbox() as sandbox:
        asyncio.run(asyncio.wait_for(prepare(settings(sandbox), identity), timeout=45))
        docker("kill", "--signal", "KILL", sandbox.name)
        docker("start", sandbox.name)
        with sandbox.client():  # Espera el reinicio antes de crear otro pool asyncio.
            pass
        asyncio.run(asyncio.wait_for(recover(settings(sandbox), identity), timeout=30))
    with RedisSandbox(appendonly=False) as sandbox:
        asyncio.run(
            asyncio.wait_for(prepare(settings(sandbox), operation_id(), enabled=False), timeout=30)
        )
    print(
        json.dumps(
            {
                "atomic_items_and_gold": True,
                "concurrent_confirm_once": True,
                "sigkill_recovery": True,
                "journal_retry_once": True,
                "reject_without_aof_before_mutation": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
