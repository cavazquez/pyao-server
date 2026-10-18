"""Coste/daño/muerte/resurrección reales y replay después de SIGKILL de Redis propio."""

import asyncio
import json
from typing import TYPE_CHECKING

from src.models.spell_catalog import SpellCatalog
from src.operations.redis_persistence import require
from src.operations.redis_sandbox import RedisSandbox, docker
from src.operations.trade_atomic_smoke import settings
from src.services.combat.pvp_policy import PvpPolicy
from src.services.combat.spell_plan import CastRequest, SpellPlan, commit_spell
from src.services.player.lifecycle import apply_player_damage, resurrect, settle_death
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_client import RedisClient
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig

FINAL_RECOVERY_STAGE = 2
INITIAL_MANA = 1000
CAST_MANA = 990
INITIAL_STAMINA = 1000
CAST_STAMINA = 999
FIRST_EXP = 950
SECOND_EXP = 903
FIRST_GOLD = 900
SECOND_GOLD = 810


async def exercise(config: RedisConfig, cast_identity: str, *, stage: int = 0) -> None:
    """Comprueba todos los recursos en el mismo Redis sintético, sin datos de producción."""
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        if stage == 0:
            for user in (1, 2):
                await client.hset(
                    RedisKeys.player_user_stats(user),
                    mapping={
                        "min_hp": "100" if user == 1 else "1",
                        "max_hp": "100",
                        "min_mana": str(INITIAL_MANA),
                        "min_sta": str(INITIAL_STAMINA),
                        "safe_mode": "0",
                        "gold": "1000",
                        "experience": "1000",
                        "life_id": "0",
                        "death_state": "alive",
                    },
                )
                await client.hset(
                    RedisKeys.player_position(user),
                    mapping={"map": "2", "x": str(49 + user), "y": "50"},
                )
                await client.hset(RedisKeys.player_spellbook(user), mapping={"2": "2"})
                await client.hset(RedisKeys.player_skills(user), mapping={"level:magia": "100"})
            await client.hset(RedisKeys.player_inventory(2), mapping={"slot_30": "199:2"})
        plan = SpellPlan(
            CastRequest(1, 2, 51, 50, 2, 2),
            dict(SpellCatalog().get_spell_data(2) or {}, id=2),
            PvpPolicy(),
        )
        result = await commit_spell(client.redis, cast_identity, plan)
        require(result["applied"] is True, "Cast y replay confirmados")
        source = await client.hgetall(RedisKeys.player_user_stats(1))
        require(int(source["min_mana"]) == CAST_MANA, "Un solo cargo de maná")
        require(int(source["min_sta"]) == CAST_STAMINA, "Un solo cargo de stamina")
        if stage == 0:
            results = await asyncio.gather(
                *(settle_death(client.redis, 2, 0, 2, 51, 50) for _ in range(2))
            )
            require(
                sum(result["applied"] for result in results) == 1, "Dos muertes liquidan una vida"
            )
        if stage < FINAL_RECOVERY_STAGE:
            dead = await client.hgetall(RedisKeys.player_user_stats(2))
            require(
                int(dead["experience"]) == FIRST_EXP and int(dead["gold"]) == FIRST_GOLD,
                "Una penalización y un drop",
            )
            require(
                dead["death_state"] == "complete" and dead["min_hp"] == "0", "Fantasma persistido"
            )
            require(
                not await client.hget(RedisKeys.player_inventory(2), "slot_30"),
                "Drop conjunto de inventario",
            )
        if stage == 1:
            require(
                not (await settle_death(client.redis, 2, 0, 2, 51, 50))["applied"],
                "Reinicio no repite pérdidas",
            )
            results = await asyncio.gather(
                *(resurrect(client.redis, 2, operation_id()) for _ in range(2))
            )
            require(sum(result["applied"] for result in results) == 1, "Una sola resurrección")
            damage = await apply_player_damage(client.redis, 2, 100, operation_id())
            require(
                damage["life_id"] == 1 and damage["player_died"], "Nueva vida permite nueva muerte"
            )
        if stage == FINAL_RECOVERY_STAGE:
            require(
                not (await settle_death(client.redis, 2, 0, 2, 51, 50))["applied"],
                "Vida vieja no liquida la nueva",
            )
            require(
                (await settle_death(client.redis, 2, 1, 2, 51, 50))["applied"],
                "Muerte pendiente recuperada",
            )
            dead = await client.hgetall(RedisKeys.player_user_stats(2))
            require(
                int(dead["experience"]) == SECOND_EXP and int(dead["gold"]) == SECOND_GOLD,
                "Nueva penalización exactamente una vez",
            )
        await require_durable(client.redis)
    finally:
        await client.disconnect()


def main() -> None:
    """Mata dos veces exclusivamente el contenedor y volumen creados por este ensayo."""
    identity = operation_id()
    with RedisSandbox() as sandbox:
        for stage in range(3):
            asyncio.run(
                asyncio.wait_for(exercise(settings(sandbox), identity, stage=stage), timeout=60)
            )
            if stage < FINAL_RECOVERY_STAGE:
                docker("kill", "--signal", "KILL", sandbox.name)
                docker("start", sandbox.name)
                with sandbox.client():
                    pass
    print(
        json.dumps(
            {
                "cost_and_effect_atomic": True,
                "death_once_per_life": True,
                "revive_once": True,
                "sigkill_recovery": True,
                "production_data_used": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
