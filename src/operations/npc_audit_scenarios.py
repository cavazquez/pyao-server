"""Pruebas breves de generación, protocolo, muerte y reaparición en Redis propio."""

import asyncio
import random
from collections import Counter
from dataclasses import asdict, replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import patch

from src.messaging.message_sender import MessageSender
from src.network.packet_id import ServerPacketID
from src.repositories.player_repository import PlayerRepository
from src.runtime_paths import data_dir
from src.services.npc.npc_death_service import NPCDeathService
from src.services.npc.npc_respawn_service import NPCRespawnService
from src.services.npc.random_spawn_service import RANDOM_SPAWN_RESPAWN_COOLDOWN, RandomSpawnService

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection
    from src.services.npc.npc_service import NPCService
    from src.utils.redis_client import RedisClient


class PacketRecorder:
    """Captura bytes producidos por MessageSender, sin simular sus serializadores."""

    address = "owned-npc-audit"
    is_authenticated = True
    capabilities = SimpleNamespace(enabled=0)

    def __init__(self) -> None:
        """Prepara un receptor de protocolo independiente."""
        self.packets: list[bytes] = []

    async def send(self, packet: bytes) -> None:
        """Conserva exactamente los bytes enviados por el código de producción."""
        self.packets.append(packet)

    def sender(self) -> MessageSender:
        """Adapta el transporte sin sustituir MessageSender.

        Returns:
            Enviador real con un receptor en memoria para el ensayo.
        """
        return MessageSender(cast("ClientConnection", self))


async def wire_sample(service: NPCService, map_ids: tuple[int, ...]) -> list[dict[str, Any]]:
    """Comprueba que dos receptores reciben los mismos NPC al entrar/reconectar.

    Returns:
        Cantidades y coincidencia de bytes; la prueba gráfica se ejecuta aparte.
    """
    result = []
    for map_id in map_ids:
        first, second = PacketRecorder(), PacketRecorder()
        await asyncio.gather(
            service.send_npcs_to_player(first.sender(), map_id),
            service.send_npcs_to_player(second.sender(), map_id),
        )
        result.append(
            {
                "map_id": map_id,
                "same_packets": first.packets == second.packets,
                "count": len(first.packets),
                "expected": len(service.map_manager.get_npcs_in_map(map_id)),
            }
        )
    return result


async def random_areas(service: NPCService, spawns: dict[int, Any], seed: int) -> dict[str, Any]:
    """Activa cada zona con dos entradas concurrentes y un reloj controlado.

    Returns:
        Cupos, posición, hostilidad y reposición antes/después del cooldown.
    """
    random.seed(seed)
    generator = RandomSpawnService(service, service.map_manager)
    generator.load_random_spawn_configs(data_dir() / "world/map_npcs.toml")
    areas, findings = [], []
    for map_id, row in spawns.items():
        for config in row.get("random_spawns", []):
            area = config["area"]
            key = generator._get_area_key(area)  # ruff: ignore[private-member-access] - etiqueta del tracker real.
            px, py = (area["x1"] + area["x2"]) // 2, (area["y1"] + area["y2"]) // 2
            await asyncio.gather(
                *(generator.spawn_random_npcs_for_player(map_id, px, py) for _ in range(2))
            )
            origin = set(generator._get_active_npcs_in_area(map_id, key))  # ruff: ignore[private-member-access] - no mezclar zonas que se superponen.
            spawned = [
                npc
                for npc in await service.npc_repository.get_all_npcs()
                if npc.instance_id in origin
            ]
            current = [
                npc
                for npc in spawned
                if area["x1"] <= npc.x <= area["x2"] and area["y1"] <= npc.y <= area["y2"]
            ]
            observation = {
                "map_id": map_id,
                "area": area,
                "expected_count": config["count"],
                "observed_count": len(current),
                "instances": [npc.instance_id for npc in current],
            }
            if len(current) != config["count"]:
                findings.append({"code": "random_area_count_mismatch", **observation})
            if len(current) != len(spawned):
                findings.append({"code": "random_spawn_outside_area", **observation})
            if config.get("npc_type") == "hostile" and any(not npc.is_hostile for npc in spawned):
                findings.append({"code": "friendly_in_hostile_area", **observation})
            if current:
                victim = current[0]
                await service.remove_npc(victim)
                await generator.on_random_npc_death(victim.instance_id)
                before_refill = len(await service.npc_repository.get_all_npcs())
                await generator.spawn_random_npcs_for_player(map_id, px, py)
                observation["immediate_refill"] = (
                    len(await service.npc_repository.get_all_npcs()) - before_refill
                )
                last_spawn = generator._respawn_cooldowns[map_id, key]  # ruff: ignore[private-member-access]
                # Reemplaza sólo la referencia de reloj de este servicio, nunca time global.
                with patch(
                    "src.services.npc.random_spawn_service.time",
                    SimpleNamespace(
                        time=lambda last_spawn=last_spawn: (
                            last_spawn + RANDOM_SPAWN_RESPAWN_COOLDOWN + 1
                        )
                    ),
                ):
                    await generator.spawn_random_npcs_for_player(map_id, px, py)
                observation["after_cooldown_count"] = len(
                    generator._get_active_npcs_in_area(map_id, key)  # ruff: ignore[private-member-access]
                )
            areas.append(observation)
    consistent = await indices_agree(service)
    if not consistent:
        findings.append({"code": "random_index_difference"})
    return {
        "seed": seed,
        "two_concurrent_entrants": True,
        "controlled_clock": True,
        "areas": areas,
        "indices_agree": consistent,
        "findings": findings,
    }


async def indices_agree(service: NPCService) -> bool:
    """Detecta escrituras huérfanas aunque no hayan llegado al tracker aleatorio.

    Returns:
        Si Redis y el índice real contienen exactamente las mismas instancias.
    """
    persistent = {
        npc.instance_id: asdict(npc) for npc in await service.npc_repository.get_all_npcs()
    }
    return persistent == {
        npc.instance_id: asdict(npc) for npc in service.map_manager.get_all_npcs()
    }


async def lifecycle(service: NPCService, client: RedisClient) -> dict[str, Any]:
    """Mata un NPC real y separa la política efectiva del timer sintético de control.

    Returns:
        Ausencia tras muerte, retiro a ambos receptores y reaparición del control.

    Raises:
        RuntimeError: Si no puede crearse el NPC de diagnóstico.
    """
    manager, repository = service.map_manager, service.npc_repository
    await client.hset(
        "player:1:user_stats",
        mapping={"level": "1", "experience": "0", "elu": "300", "min_hp": "100", "max_hp": "100"},
    )
    respawn = NPCRespawnService(service)
    death = NPCDeathService(
        manager,
        repository,
        PlayerRepository(client),
        service.broadcast_service,
        npc_respawn_service=respawn,
    )
    first, second = PacketRecorder(), PacketRecorder()
    for user, sender in enumerate((first.sender(), second.sender()), 1):
        manager.add_player(290, user, sender, f"Audit{user}")
    point = next(
        (x, y) for x in range(20, 80) for y in range(20, 80) if manager.can_move_to(290, x, y)
    )
    control = await service.spawn_npc(504, 290, *point)
    if control is None:
        message = "NPC de control ausente"
        raise RuntimeError(message)
    # El único override es sobre una instancia de diagnóstico; el catálogo permanece intacto.
    control = replace(control, respawn_time=1, respawn_time_max=1)
    await client.hset(
        f"npc:instance:{control.instance_id}",
        mapping={
            "hp": "0",
            "respawn_time": "1",
            "respawn_time_max": "1",
            "death_state": "pending",
            "death_killer": "1",
        },
    )
    before = {npc.instance_id for npc in manager.get_npcs_in_map(290)}
    first.packets.clear()
    second.packets.clear()
    await death.handle_npc_death(control, 1, 0, first.sender())
    removed = await repository.get_npc(control.instance_id) is None and all(
        npc.instance_id != control.instance_id for npc in manager.get_npcs_in_map(290)
    )
    removals = [
        sum(packet[0] == ServerPacketID.CHARACTER_REMOVE for packet in recorder.packets)
        for recorder in (first, second)
    ]
    tasks = tuple(respawn._respawn_tasks.values())  # ruff: ignore[private-member-access] - esperar y limpiar todas las tareas propias.
    try:
        async with asyncio.timeout(8):
            await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for user in (1, 2):
            manager.remove_player(290, user)
    new = [npc for npc in manager.get_npcs_in_map(290) if npc.instance_id not in before]
    policy = await respawn_policies(service)
    if not removed or removals != [1, 1] or len(new) != 1:
        policy["findings"].append({"code": "controlled_lifecycle_failed"})
    return {
        "removed_from_redis_and_map": removed,
        "removal_packets_per_client": removals,
        "controlled_respawn_seconds": 1,
        "controlled_respawn_count": len(new),
        "control_does_not_prove_catalog_respawns": True,
        **policy,
    }


async def respawn_policies(service: NPCService) -> dict[str, Any]:
    """Separa las declaraciones de reaparición de los timers efectivos.

    Returns:
        Conteos reales y plantillas cuyo flag no se traduce a un timer.
    """
    row_counts = Counter(
        npc.respawn_time > 0
        for npc in await service.npc_repository.get_all_npcs()
        if not npc.is_tamed
    )
    unmapped = [
        npc_id
        for npc_id in service.npc_catalog.get_all_npc_ids()
        if (row := service.npc_catalog.get_npc_data(npc_id))
        and isinstance(row.get("behavior"), dict)
        and cast("dict[str, Any]", row["behavior"]).get("respawn")
        and not row.get("respawn_time")
    ]
    findings: list[dict[str, Any]] = [
        {"code": "respawn_policy_unmapped", "npc_id": npc_id} for npc_id in unmapped
    ]
    return {
        "normal_npcs_with_timer": row_counts[True],
        "normal_npcs_without_timer": row_counts[False],
        "findings": findings,
    }
