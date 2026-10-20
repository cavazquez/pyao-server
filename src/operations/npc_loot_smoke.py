"""Botín real, plan pendiente, AOF y recogida concurrente sobre Redis descartable."""

import asyncio
import json
import time
from typing import TYPE_CHECKING, Any, cast

from src.models.item_constants import GOLD_ITEM_ID
from src.operations.npc_commerce_smoke import settings
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.repositories.inventory_repository import InventoryRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.services.ground_transfer import GroundRequest, transfer_ground
from src.services.npc.loot_table_service import LootTableService
from src.services.npc.rewards.settlement import death_changes, settle_rewards
from src.services.nutrition import NutritionRule, consume_nutrition
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.ground_state import GroundState, stack_identity
from src.utils.ground_storage import encode_fields, read_ground
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from collections.abc import Mapping

    from redis.typing import EncodableT

    from src.config.game_config import RedisConfig
    from src.models.npc import NPC

MAX_FIXTURE_ATTEMPTS = 200
MAP_ID = 2
DROP_POSITION = (49, 49)
EXPERIENCE = 123


async def candidate(repository: NPCRepository, policy: LootTableService) -> NPC:
    """Elige un UUID que dé oro y equipo con la política real, sin sustituir el RNG.

    Returns:
        Instancia de diagnóstico muerta con el sorteo de producción aún sin liquidar.

    Raises:
        RuntimeError: Si no se obtiene un caso útil dentro del presupuesto del fixture.
    """
    for _ in range(MAX_FIXTURE_ATTEMPTS):
        npc = await repository.create_npc_instance(
            npc_id=505,
            char_index=10001,
            map_id=MAP_ID,
            x=50,
            y=50,
            heading=3,
            name="Fixture loot AOF",
            description="No pertenece a un mundo productivo",
            body_id=14,
            head_id=0,
            hp=0,
            max_hp=100,
            level=100,
            is_hostile=True,
            is_attackable=True,
            loot_profile="boss",
            respawn_time=0,
            respawn_time_max=0,
            gold_min=50000,
            gold_max=50000,
        )
        rolled = policy.roll(npc)
        if any(i == GOLD_ITEM_ID for i, _ in rolled) and any(
            i != GOLD_ITEM_ID
            and policy.item_rules.categories[policy.item_rules.items[i].category]["slot"]
            == "equipment"
            for i, _ in rolled
        ):
            await repository.redis.hset(
                RedisKeys.npc_instance(npc.instance_id), mapping=death_changes(0, 1)
            )
            return npc
        await repository.remove_npc(npc.instance_id)
    message = "No se obtuvo una muestra de oro y equipo para el ensayo AOF"
    raise RuntimeError(message)


async def prepare(config: RedisConfig) -> str:
    """Congela un plan sobre un suelo sin espacio y comprueba que no paga por partes.

    Returns:
        UUID que debe conservar el plan después de matar el proceso Redis.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        for user in (1, 2):
            await client.hset(
                RedisKeys.player_user_stats(user),
                mapping={
                    "level": "10",
                    "experience": "0",
                    "elu": "100000",
                    "min_hp": "100",
                    "max_hp": "100",
                    "gold": "0",
                },
            )
            await PlayerRepository(client).set_position(user, *DROP_POSITION, MAP_ID, 3)
        npc = await candidate(NPCRepository(client), LootTableService())
        await client.hset(
            RedisKeys.npc_instance(npc.instance_id), "fixture_food_operation", operation_id()
        )
        await InventoryRepository(client).set_slot(1, 30, 139, 1)
        await client.hset(
            RedisKeys.player_hunger_thirst(1),
            mapping={"min_hunger": "0", "max_hunger": "100", "min_water": "0", "max_water": "100"},
        )
        full = GroundState(MAP_ID, None)
        for index in range(10):
            full.append(
                *DROP_POSITION,
                {"item_id": 1, "quantity": 1, "stack_id": stack_identity(f"occupied:{index}")},
            )
        await client.redis.hset(
            RedisKeys.ground_items(MAP_ID),
            mapping=cast("Mapping[EncodableT, EncodableT]", encode_fields(full)),
        )
        result = await settle_rewards(
            client.redis, npc, 1, EXPERIENCE, LootTableService(), (DROP_POSITION,)
        )
        require(not result["settled"] and result["pending"], "Plan pendiente por capacidad")
        require(
            await client.hget(RedisKeys.player_user_stats(1), "experience") == "0", "Sin XP parcial"
        )
        require(
            (await read_ground(client.redis, MAP_ID)).encode() == full.encode(), "Sin botín parcial"
        )
        require(
            bool(await client.hget(RedisKeys.npc_instance(npc.instance_id), "reward_plan")),
            "Plan congelado durable",
        )
        await require_durable(client.redis)
        return npc.instance_id
    finally:
        await client.disconnect()


async def recover(config: RedisConfig, identity: str) -> dict[str, Any]:
    """Recupera, disputa cada pila entre dos jugadores y vuelve a reproducir la muerte.

    Returns:
        Inventarios/saldos/XP que deben ser idénticos tras otro SIGKILL.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        repository, policy = NPCRepository(client), LootTableService()
        npc = await repository.get_npc(identity)
        require(npc is not None, "Cadáver y plan recuperados de AOF")
        assert npc is not None  # ruff: ignore[assert] - diagnóstico ya comprobado por require.
        saved = json.loads(
            await client.hget(RedisKeys.npc_instance(identity), "reward_plan") or "{}"
        )
        await client.delete(RedisKeys.ground_items(MAP_ID))
        results = await asyncio.gather(
            *(
                settle_rewards(client.redis, npc, 1, EXPERIENCE, policy, (DROP_POSITION,))
                for _ in range(3)
            )
        )
        require(sum(row["applied"] for row in results) == 1, "Una liquidación concurrente")
        ground = await read_ground(client.redis, MAP_ID)
        actual = ground.tile(*DROP_POSITION)
        require(
            sorted((r["item_id"], r["quantity"]) for r in actual)
            == sorted(map(tuple, saved["items"])),
            "Se conserva exactamente el sorteo previo a la caída",
        )
        require(len({r["stack_id"] for r in actual}) == len(actual), "Identidades únicas")
        for item in actual:
            actions = await asyncio.gather(
                *(
                    transfer_ground(
                        client.redis,
                        GroundRequest(
                            user,
                            MAP_ID,
                            *DROP_POSITION,
                            "pickup",
                            expected_stack=str(item["stack_id"]),
                        ),
                        operation_id(),
                        30,
                        20,
                    )
                    for user in (1, 2)
                )
            )
            require(sum(row["applied"] for row in actions) == 1, "Una sola recogida por identidad")
        await settle_rewards(client.redis, npc, 1, EXPERIENCE, policy, (DROP_POSITION,))
        food = NutritionRule.from_item(139, policy.catalog.get_item_data(139) or {})
        consumed = await consume_nutrition(
            client.redis,
            1,
            30,
            await client.hget(RedisKeys.npc_instance(identity), "fixture_food_operation") or "",
            food,
            30,
            20,
        )
        require(consumed["applied"], "Consumo real de pescado con su efecto")
        require(
            await client.hget(RedisKeys.player_hunger_thirst(1), "min_hunger") == "75",
            "Hambre restaurada según catálogo",
        )
        inventories = [await InventoryRepository(client).get_inventory(user) for user in (1, 2)]
        balances = [await PlayerRepository(client).get_gold(user) for user in (1, 2)]
        expected_gold = sum(q for i, q in saved["items"] if i == GOLD_ITEM_ID)
        require(
            sum(balances) == expected_gold, "Oro exacto conservado tras dos recogidas competidoras"
        )
        for item_id, quantity in saved["items"]:
            if item_id != GOLD_ITEM_ID:
                require(
                    sum(
                        int(row.split(":")[1])
                        for inv in inventories
                        for row in inv.values()
                        if row.startswith(f"{item_id}:")
                    )
                    == quantity,
                    "Objetos exactos conservados",
                )
        xp = await client.hget(RedisKeys.player_user_stats(1), "experience")
        require(xp == str(EXPERIENCE), "XP acreditada una sola vez")
        require(
            not (await read_ground(client.redis, MAP_ID)).tile(*DROP_POSITION),
            "Replay no regenera pilas recogidas",
        )
        await require_durable(client.redis)
        return {
            "inventories": inventories,
            "balances": balances,
            "experience": xp,
            "items": saved["items"],
        }
    finally:
        await client.disconnect()


async def verify(config: RedisConfig, identity: str, before: dict[str, Any]) -> None:
    """Después de otra caída, un replay no vuelve a llenar el suelo ni sumar XP."""
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        npc = await NPCRepository(client).get_npc(identity)
        require(npc is not None, "Cadáver completo recuperado")
        assert npc is not None  # ruff: ignore[assert] - se requiere una instancia para el replay.
        result = await settle_rewards(
            client.redis, npc, 1, EXPERIENCE, LootTableService(), (DROP_POSITION,)
        )
        require(
            result["settled"] and not result["applied"],
            "Recibo durable rechaza la segunda recompensa",
        )
        food = NutritionRule.from_item(139, LootTableService().catalog.get_item_data(139) or {})
        await consume_nutrition(
            client.redis,
            1,
            30,
            await client.hget(RedisKeys.npc_instance(identity), "fixture_food_operation") or "",
            food,
            30,
            20,
        )
        require(
            await client.hget(RedisKeys.player_hunger_thirst(1), "min_hunger") == "75",
            "Replay AOF no duplica el efecto de la comida",
        )
        require(
            [await InventoryRepository(client).get_inventory(u) for u in (1, 2)]
            == before["inventories"],
            "Inventarios conservados tras AOF",
        )
        require(
            [await PlayerRepository(client).get_gold(u) for u in (1, 2)] == before["balances"],
            "Saldos conservados tras AOF",
        )
        require(
            await client.hget(RedisKeys.player_user_stats(1), "experience") == before["experience"],
            "XP conservada tras AOF",
        )
        require(
            not (await read_ground(client.redis, MAP_ID)).tile(*DROP_POSITION),
            "Suelo sin duplicados tras AOF",
        )
    finally:
        await client.disconnect()


def main() -> None:
    """Crea y elimina exclusivamente su contenedor/volumen y nunca usa Redis del operador."""
    start = time.monotonic()
    with RedisSandbox() as sandbox:
        identity = asyncio.run(prepare(settings(sandbox)))
        for stage in range(2):
            docker("kill", "--signal", "KILL", sandbox.name)
            docker("start", sandbox.name)
            with sandbox.client():
                pass
            if stage == 0:
                result = asyncio.run(recover(settings(sandbox), identity))
            else:
                asyncio.run(verify(settings(sandbox), identity, result))
    print(
        json.dumps(
            {
                "pending_plan_recovered": True,
                "single_roll_and_xp": True,
                "two_competing_pickups_per_stack": True,
                "two_aof_sigkill_recoveries": True,
                "production_data_used": False,
                "elapsed_seconds": round(time.monotonic() - start, 2),
                **result,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
