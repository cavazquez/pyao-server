"""La auditoría distingue un ensayo ejecutado de un mundo válido y no oculta datos."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

import pytest

from src.game.map_manager import MapManager
from src.models.npc import NPC
from src.models.npc_catalog import NPCCatalog
from src.operations.npc_audit_report import compare_world, original_sounds, roles, sound_inventory
from src.operations.npc_audit_scenarios import PacketRecorder, random_areas, wire_sample
from src.repositories.account_repository import AccountRepository
from src.repositories.npc_repository import NPCRepository
from src.repositories.player_repository import PlayerRepository
from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.services.npc.npc_service import NPCService


@pytest.fixture
def catalog(tmp_path):
    """Catálogo mínimo con un servicio amistoso y una criatura atacable."""
    result = NPCCatalog(str(tmp_path / "absent-hostile"), str(tmp_path / "absent-friendly"))
    result._npcs = {
        1: {
            "nombre": "Comerciante",
            "body_id": 18,
            "head_id": 0,
            "es_mercader": True,
            "es_hostil": False,
            "es_atacable": False,
        },
        504: {
            "nombre": "Serpiente",
            "body_id": 13,
            "head_id": 0,
            "es_hostil": True,
            "es_atacable": True,
        },
    }
    return result


def creature():
    """Instancia separada del catálogo: modificar una expectativa debe detectarse."""
    return NPC(
        npc_id=504,
        char_index=10001,
        instance_id="snake",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Serpiente",
        description="",
        body_id=13,
        head_id=0,
        hp=22,
        max_hp=22,
        level=1,
        is_hostile=True,
        is_attackable=True,
    )


def world(_catalog, point=None, observed=None):
    """Prepara dos mapas, uno explícitamente vacío."""
    manager = MapManager()
    manager._map_sizes = {1: (100, 100), 2: (100, 100)}
    manager._blocked_tiles = {1: set(), 2: set()}
    npcs = [creature()] if observed is None else observed
    for npc in npcs:
        manager.add_npc(npc.map_id, npc)
    config = {1: {"spawn_points": [point or {"npc_id": 504, "x": 50, "y": 50, "direction": 3}]}}
    return manager, config, npcs


def test_empty_map_remains_in_report(catalog):
    """Ausencia de configuración no se convierte en un NPC faltante."""
    manager, config, observed = world(catalog)
    report = compare_world({1: {}, 2: {}}, config, catalog, manager, observed)
    assert report["findings"] == []
    assert len(report["maps"]) == 2
    empty = report["maps"][1]
    assert empty["loaded"]
    assert not empty["has_npc_configuration"]
    assert empty["observed"] == empty["expected_fixed"] == []


@pytest.mark.parametrize(
    ("change", "expected_code"),
    [
        ({"direction": 1}, "runtime_field_mismatch"),
        ({"npc_id": 99999}, "missing_catalog_npc"),
        ({"x": 101}, "out_of_bounds"),
    ],
)
def test_configuration_changes_cannot_use_runtime_as_expectation(catalog, change, expected_code):
    """Un ID o heading incorrectos no pasan aunque Redis y MapManager coincidan."""
    manager, config, observed = world(catalog)
    config[1]["spawn_points"][0].update(change)
    report = compare_world({1: {}}, config, catalog, manager, observed)
    assert expected_code in report["summary"]


def test_blocked_and_enclosed_tile_is_not_masked_by_occupation(catalog):
    """Un NPC instanciado correctamente puede estar físicamente inaccesible."""
    manager, config, observed = world(catalog)
    manager._blocked_tiles[1] = {(50, 50), (49, 50), (51, 50), (50, 49), (50, 51)}
    report = compare_world({1: {}}, config, catalog, manager, observed)
    assert report["summary"] == {"blocked_spawn": 1, "no_adjacent_walkable_tile": 1}


def test_missing_and_extra_instances_are_counted_independently(catalog):
    """Igual cantidad total no oculta un spawn en otra coordenada."""
    manager, config, observed = world(catalog, observed=[replace(creature(), x=51)])
    report = compare_world({1: {}}, config, catalog, manager, observed)
    assert report["summary"] == {"missing_fixed_spawn": 1, "unexpected_fixed_spawn": 1}


def test_orphan_in_redis_and_duplicate_are_detected(catalog):
    """Una escritura que no llegó al índice no desaparece del informe."""
    manager, config, observed = world(catalog)
    observed.append(replace(creature(), instance_id="orphan", char_index=10002))
    report = compare_world({1: {}}, config, catalog, manager, observed)
    assert report["summary"] == {
        "unexpected_fixed_spawn": 1,
        "duplicate_tile": 1,
        "redis_map_index_difference": 1,
    }


def test_pets_are_not_extra_fixed_inhabitants(catalog):
    """Mascotas e invocaciones conservan su instancia y categoría separada."""
    manager, config, observed = world(
        catalog,
        observed=[
            creature(),
            replace(
                creature(),
                instance_id="pet",
                char_index=10002,
                x=55,
                is_tamed=True,
                summoned_by_user_id=5,
            ),
        ],
    )
    report = compare_world({1: {}}, config, catalog, manager, observed)
    assert report["findings"] == []
    assert report["maps"][0]["pets_and_summons"] == 1


def test_roles_do_not_imply_hostility_or_attackability():
    """Un guardia atacable y amistoso no se transforma en monstruo hostil."""
    row = {"nombre": "Guardia Real", "es_atacable": True, "es_hostil": False}
    assert roles(row) == ["guard_hint"]
    assert not row["es_hostil"]


def test_historical_sound_slots_preserve_holes_case_and_order(tmp_path):
    """SND2 aislado nunca se desplaza al slot de ataque."""
    dat = tmp_path / "NPCs.dat"
    dat.write_bytes(b"[NPC504]\nName=Serpiente\nSND3=62\nSnd2 = 103\n[NPC1]\nName=Aldeano\n")
    assert original_sounds(dat) == {504: [0, 103, 62], 1: [0, 0, 0]}


def test_missing_configuration_is_separate_from_intentional_silence(catalog, tmp_path):
    """Un catálogo entero sin sonido no acredita que el audio funcione."""
    catalog._npcs[1]["appearance"] = {"sounds": [0, 0, 0]}
    dat = tmp_path / "NPCs.dat"
    dat.write_text("[NPC504]\nSnd2=103\n")
    report = sound_inventory(catalog, tmp_path, dat)
    assert report["npcs_without_sound_configuration"] == 1
    assert report["historical_npcs_with_sound"] == 1
    assert report["historical_missing_assets"] == [103]
    assert report["findings"][0]["code"] == "historical_sound_difference"


def test_current_missing_and_unrepresentable_sound_ids(catalog, tmp_path):
    """El byte inválido y el WAV ausente se localizan por NPC y slot."""
    catalog._npcs[504]["appearance"] = {"sounds": [0, 174, 256]}
    report = sound_inventory(catalog, tmp_path, None)
    assert {finding["code"] for finding in report["findings"]} == {
        "invalid_sound_id",
        "missing_sound_asset",
    }
    assert report["client_resources_checked"]


@pytest.mark.asyncio
async def test_real_serializers_send_identical_world_to_two_receivers(catalog, redis_client):
    """El ensayo no reemplaza el constructor de paquetes por un mock."""
    from src.repositories.account_repository import AccountRepository  # ruff: ignore[import-outside-top-level]
    from src.repositories.player_repository import PlayerRepository  # ruff: ignore[import-outside-top-level]

    NPCService.reset_instance()
    manager = MapManager()
    broadcast = MultiplayerBroadcastService(
        manager, PlayerRepository(redis_client), AccountRepository(redis_client)
    )
    service = NPCService(NPCRepository(redis_client), catalog, manager, broadcast)
    try:
        await service.spawn_npc(504, 1, 50, 50)
        assert await wire_sample(service, (1, 2)) == [
            {"map_id": 1, "same_packets": True, "count": 1, "expected": 1},
            {"map_id": 2, "same_packets": True, "count": 0, "expected": 0},
        ]
    finally:
        NPCService.reset_instance()


@pytest.mark.asyncio
@pytest.mark.parametrize(("event", "wave"), [("attack", 47), ("hurt", 103), ("death", 62)])
async def test_specific_npc_voice_reaches_both_real_packet_serializers(
    catalog, redis_client, event, wave, monkeypatch
):
    """Control de enrutamiento: no confunde SwordHit con la voz del NPC.

    Para daño físico se fija sólo el resultado del combate; no acredita el
    cálculo de daño ni la configuración ausente del catálogo de producción.
    """
    from src.command_handlers.attack_execution_handler import AttackExecutionHandler  # ruff: ignore[import-outside-top-level]
    from src.services.npc.npc_ai_service import NPCAIService  # ruff: ignore[import-outside-top-level]
    from src.services.npc.npc_death_service import NPCDeathService  # ruff: ignore[import-outside-top-level]

    catalog._npcs[504]["appearance"] = {"sounds": [47, 103, 62]}
    NPCService.reset_instance()
    manager = MapManager()
    player = PlayerRepository(redis_client)
    broadcast = MultiplayerBroadcastService(manager, player, AccountRepository(redis_client))
    service = NPCService(NPCRepository(redis_client), catalog, manager, broadcast)
    recorders = [PacketRecorder(), PacketRecorder()]
    try:
        npc = await service.spawn_npc(504, 1, 50, 50)
        assert npc is not None
        assert (npc.snd1, npc.snd2, npc.snd3) == (47, 103, 62)
        for user_id, recorder in enumerate(recorders, 1):
            manager.add_player(1, user_id, recorder.sender(), "Synthetic")
        if event == "attack":
            ai = NPCAIService(service, manager, player, None, broadcast)
            await ai._send_attack_effects(npc, 1, 1)
        elif event == "hurt":
            combat = AsyncMock()
            combat.player_attack_npc.return_value = {
                "damage": 1,
                "critical": False,
                "npc_died": False,
            }
            handler = AttackExecutionHandler(combat, broadcast, recorders[0].sender())
            success, _, _ = await handler.execute_attack(1, npc, 50, 50)
            assert success
        else:
            await redis_client.hset(
                "player:1:user_stats", mapping={"level": "1", "experience": "0", "elu": "300"}
            )
            await redis_client.hset(f"npc:instance:{npc.instance_id}", "hp", "0")
            monkeypatch.setattr("src.services.npc.rewards.settlement.require_durable", AsyncMock())
            death = NPCDeathService(manager, service.npc_repository, player, broadcast)
            await death.handle_npc_death(npc, 1, 0, recorders[0].sender())
        assert all(bytes([39, wave, 50, 50]) in recorder.packets for recorder in recorders)
    finally:
        NPCService.reset_instance()


@pytest.mark.asyncio
async def test_overlapping_areas_use_origin_instead_of_geometric_double_count(
    catalog, redis_client, tmp_path, monkeypatch
):
    """Dos zonas activadas juntas se atribuyen al origen, aunque se superpongan."""
    from src.repositories.account_repository import AccountRepository  # ruff: ignore[import-outside-top-level]
    from src.repositories.player_repository import PlayerRepository  # ruff: ignore[import-outside-top-level]

    directory = tmp_path / "world"
    directory.mkdir()
    (directory / "map_npcs.toml").write_text(
        "[map_npcs.1]\n"
        '[[map_npcs.1.random_spawns]]\nnpc_type="hostile"\ncount=2\n'
        "[map_npcs.1.random_spawns.area]\nx1=20\ny1=20\nx2=80\ny2=80\n"
        '[[map_npcs.1.random_spawns]]\nnpc_type="hostile"\ncount=3\n'
        "[map_npcs.1.random_spawns.area]\nx1=40\ny1=40\nx2=60\ny2=60\n"
    )
    monkeypatch.setattr("src.operations.npc_audit_scenarios.data_dir", lambda: tmp_path)
    NPCService.reset_instance()
    manager = MapManager()
    broadcast = MultiplayerBroadcastService(
        manager, PlayerRepository(redis_client), AccountRepository(redis_client)
    )
    service = NPCService(NPCRepository(redis_client), catalog, manager, broadcast)
    original = service.spawn_npc

    async def interleave(*args: int, **kwargs: int):
        await asyncio.sleep(0)
        return await original(*args, **kwargs)

    monkeypatch.setattr(service, "spawn_npc", interleave)
    try:
        spawns = {
            1: {
                "random_spawns": [
                    {
                        "npc_type": "hostile",
                        "count": 2,
                        "area": {"x1": 20, "y1": 20, "x2": 80, "y2": 80},
                    },
                    {
                        "npc_type": "hostile",
                        "count": 3,
                        "area": {"x1": 40, "y1": 40, "x2": 60, "y2": 60},
                    },
                ]
            }
        }
        result = await random_areas(service, spawns, 307)
        # Las entradas concurrentes respetan el cupo y conservan el origen.
        assert [row["observed_count"] for row in result["areas"]] == [2, 3]
        assert result["findings"] == []
        assert result["indices_agree"]
    finally:
        NPCService.reset_instance()
