"""Auditoría reproducible de NPCs sobre Redis AOF descartable propio.

No acepta un endpoint Redis: el comando crea y retira sus recursos. Devuelve 1
si encuentra discrepancias; detectar un defecto no acredita un mundo correcto.
"""

import argparse
import asyncio
import json
import logging
import random
from collections import Counter
from pathlib import Path
from typing import TYPE_CHECKING, Any

from src.core.server_initializer import ServerInitializer
from src.game.map_manager import MapManager
from src.models.npc_catalog import NPCCatalog
from src.operations.npc_audit_report import compare_world, configuration, sound_inventory
from src.operations.npc_audit_scenarios import lifecycle, random_areas, wire_sample
from src.operations.npc_commerce_smoke import settings
from src.operations.redis_sandbox import RedisSandbox
from src.repositories.account_repository import AccountRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.runtime_paths import data_dir
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.services.npc.npc_service import NPCService
from src.utils.durability import require_durable
from src.utils.redis_client import RedisClient

if TYPE_CHECKING:
    from src.config.game_config import RedisConfig


def runtime(client: RedisClient) -> NPCService:
    """Inicializa los mismos servicios, catálogo y tiles que usa el servidor.

    Returns:
        Servicio real con índices nuevos, conservando la base del ensayo.
    """
    NPCService.reset_instance()
    manager = MapManager()
    ServerInitializer._load_map_tiles(manager)  # ruff: ignore[private-member-access] - mismo loader del arranque real.
    repository = NPCRepository(client)
    broadcast = MultiplayerBroadcastService(
        manager, PlayerRepository(client), AccountRepository(client)
    )
    return NPCService(repository, NPCCatalog(), manager, broadcast)


async def snapshot(config: RedisConfig, *, restarted: bool, seed: int) -> dict[str, Any]:
    """Contrasta el mundo completo y ejercita sólo ciclos breves de NPC.

    Returns:
        Expectativas, observaciones y pruebas independientes por etapa.

    Raises:
        RuntimeError: Si no puede prepararse la mascota de diagnóstico.
    """
    client = RedisClient()
    await client.connect(config, seed_defaults=False)
    try:
        service = runtime(client)
        persisted = await service.npc_repository.get_all_npcs()
        await service.initialize_world_npcs()
        observed = await service.npc_repository.get_all_npcs()
        maps, spawns = configuration(data_dir())
        report = compare_world(maps, spawns, service.npc_catalog, service.map_manager, observed)
        report["persisted_before_boot"] = len(persisted)
        report["normal_count"] = sum(
            not npc.is_tamed and not npc.summoned_by_user_id for npc in observed
        )
        report["pet_ids"] = sorted(npc.instance_id for npc in observed if npc.is_tamed)
        report["normal_instance_ids"] = sorted(
            npc.instance_id for npc in observed if not npc.is_tamed
        )
        if restarted:
            report["wire_samples"] = await wire_sample(service, (1, 34, 290))
            report["random_generation"] = await random_areas(service, spawns, seed)
            report["lifecycle"] = await lifecycle(service, client)
        else:
            # Mascota sintética separada de los habitantes. Sólo escribe en el Redis propio.
            x, y = next(
                (x, y)
                for x in range(2, 99)
                for y in range(2, 99)
                if service.map_manager.can_move_to(290, x, y)
            )
            pet = await service.spawn_npc(504, 290, x, y)
            if pet is None:
                message = "No se pudo preparar la mascota de control"
                raise RuntimeError(message)
            await client.hset(
                f"npc:instance:{pet.instance_id}",
                mapping={"is_tamed": "True", "summoned_by_user_id": "1"},
            )
            report["prepared_pet_id"] = pet.instance_id
        await require_durable(client.redis)
        return report
    finally:
        NPCService.reset_instance()
        await client.disconnect()


def audit(client: Path | None, original: Path | None, seed: int) -> dict[str, Any]:
    """Ejecuta arranque vacío y recreación de Redis conservando su AOF.

    Returns:
        Informe completo; los fallos de contenido no se silencian ni reparan.
    """
    random_state = random.getstate()
    try:
        random.seed(seed)
        with RedisSandbox() as sandbox:
            cold = asyncio.run(snapshot(settings(sandbox), restarted=False, seed=seed))
            sandbox.recreate(appendonly=True)
            warm = asyncio.run(snapshot(settings(sandbox), restarted=True, seed=seed))
    finally:
        random.setstate(random_state)
    sounds = sound_inventory(NPCCatalog(), client, original)
    unchanged = cold["normal_count"] == warm["normal_count"]
    preserved_pet = warm["pet_ids"] == [cold["prepared_pet_id"]]
    rebuilt = not set(cold["normal_instance_ids"]) & set(warm["normal_instance_ids"])
    findings = [
        *cold["findings"],
        *sounds["findings"],
        *warm["random_generation"]["findings"],
        *warm["lifecycle"]["findings"],
    ]
    findings.extend(
        {"stage": "restart", **finding}
        for finding in warm["findings"]
        if finding not in cold["findings"]
    )
    if not unchanged or not preserved_pet or not rebuilt:
        findings.append({"code": "restart_population_difference"})
    findings.extend(
        {"code": "wire_population_difference", **sample}
        for sample in warm["wire_samples"]
        if not sample["same_packets"] or sample["count"] != sample["expected"]
    )
    return {
        "schema": 1,
        "seed": seed,
        "production_data_used": False,
        "audit_executed": True,
        "world_checks_passed": not findings,
        "maps_checked": len(cold["maps"]),
        "fixed_npcs": cold["normal_count"],
        "maps_without_npc_configuration": [
            row["map_id"] for row in cold["maps"] if not row["has_npc_configuration"]
        ],
        "cold_start": cold,
        "persisted_restart": warm,
        "sounds": sounds,
        "restart": {
            "fixed_population_unchanged": unchanged,
            "pet_preserved": preserved_pet,
            "normal_instances_rebuilt": rebuilt,
            "aof_recreated": True,
        },
        "findings": findings,
        "summary": dict(Counter(finding["code"] for finding in findings)),
        "gameplay_campaign_executed": False,
    }


def main() -> None:
    """Escribe evidencia incluso cuando hay discrepancias.

    Raises:
        SystemExit: Código 1 si la auditoría encuentra problemas del mundo.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--client", type=Path, help="Checkout del cliente para comprobar WAV")
    parser.add_argument("--original-npcs", type=Path, help="DAT histórico, sólo como referencia")
    parser.add_argument("--seed", type=int, default=307)
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING)
    report = audit(args.client, args.original_npcs, args.seed)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "audit_executed",
                    "world_checks_passed",
                    "maps_checked",
                    "fixed_npcs",
                    "summary",
                )
            }
        )
    )
    raise SystemExit(0 if report["world_checks_passed"] else 1)


if __name__ == "__main__":
    main()
