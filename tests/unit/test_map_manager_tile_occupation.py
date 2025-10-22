"""Tests para verificar que _tile_occupation se limpia correctamente al remover NPCs."""

import pytest

from src.game.map_manager import MapManager
from src.models.npc import NPC


@pytest.fixture
def map_manager():
    """Fixture que crea un MapManager."""
    return MapManager()


@pytest.fixture
def sample_npc():
    """Fixture que crea un NPC de prueba."""
    return NPC(
        npc_id=1,
        char_index=10001,
        instance_id="test_npc_001",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Goblin",
        description="Un goblin hostil",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=True,
        is_attackable=True,
        movement_type="static",
        respawn_time=30,
        respawn_time_max=60,
        gold_min=10,
        gold_max=50,
    )


def test_tile_occupation_cleared_when_npc_removed(map_manager, sample_npc):
    """Verifica que _tile_occupation se limpia al remover un NPC.

    Este test reproduce el bug donde los tiles quedaban bloqueados
    después de remover un NPC, impidiendo que los jugadores se movieran
    sobre el oro dropeado.
    """
    # Agregar NPC al mapa
    map_manager.add_npc(sample_npc.map_id, sample_npc)

    # Verificar que el tile está ocupado
    assert map_manager.is_tile_occupied(sample_npc.map_id, sample_npc.x, sample_npc.y)
    occupant = map_manager.get_tile_occupant(sample_npc.map_id, sample_npc.x, sample_npc.y)
    assert occupant == f"npc:{sample_npc.instance_id}"

    # Verificar que can_move_to retorna False (tile bloqueado)
    assert not map_manager.can_move_to(sample_npc.map_id, sample_npc.x, sample_npc.y)

    # Remover NPC
    map_manager.remove_npc(sample_npc.map_id, sample_npc.instance_id)

    # Verificar que el tile ya NO está ocupado
    assert not map_manager.is_tile_occupied(sample_npc.map_id, sample_npc.x, sample_npc.y)

    # Verificar que can_move_to retorna True (tile libre)
    assert map_manager.can_move_to(sample_npc.map_id, sample_npc.x, sample_npc.y)


def test_tile_occupation_with_multiple_npcs(map_manager):
    """Verifica que solo se limpia el tile del NPC removido."""
    # Crear dos NPCs en diferentes posiciones
    npc1 = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="npc_001",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Goblin",
        description="Un goblin hostil",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=True,
        is_attackable=True,
        movement_type="static",
        respawn_time=30,
        respawn_time_max=60,
        gold_min=10,
        gold_max=50,
    )

    npc2 = NPC(
        npc_id=2,
        char_index=10002,
        instance_id="npc_002",
        map_id=1,
        x=51,
        y=50,
        heading=3,
        name="Lobo",
        description="Un lobo salvaje",
        body_id=2,
        head_id=2,
        hp=80,
        max_hp=80,
        level=2,
        is_hostile=True,
        is_attackable=True,
        movement_type="random",
        respawn_time=30,
        respawn_time_max=60,
        gold_min=20,
        gold_max=60,
    )

    # Agregar ambos NPCs
    map_manager.add_npc(npc1.map_id, npc1)
    map_manager.add_npc(npc2.map_id, npc2)

    # Verificar que ambos tiles están ocupados
    assert map_manager.is_tile_occupied(npc1.map_id, npc1.x, npc1.y)
    assert map_manager.is_tile_occupied(npc2.map_id, npc2.x, npc2.y)

    # Remover solo el primer NPC
    map_manager.remove_npc(npc1.map_id, npc1.instance_id)

    # Verificar que solo el tile del NPC removido se liberó
    assert not map_manager.is_tile_occupied(npc1.map_id, npc1.x, npc1.y)
    assert map_manager.is_tile_occupied(npc2.map_id, npc2.x, npc2.y)

    # Verificar can_move_to
    assert map_manager.can_move_to(npc1.map_id, npc1.x, npc1.y)  # Libre
    assert not map_manager.can_move_to(npc2.map_id, npc2.x, npc2.y)  # Ocupado


def test_remove_npc_nonexistent_does_not_crash(map_manager):
    """Verifica que remover un NPC inexistente no causa errores."""
    # Intentar remover un NPC que no existe
    map_manager.remove_npc(map_id=1, instance_id="nonexistent_npc")

    # No debería causar ningún error
    assert True


def test_cannot_add_two_npcs_same_position(map_manager):
    """Verifica que no se pueden agregar dos NPCs en la misma posición."""
    npc1 = NPC(
        npc_id=1,
        char_index=10001,
        instance_id="npc_001",
        map_id=1,
        x=50,
        y=50,
        heading=3,
        name="Goblin",
        description="Un goblin hostil",
        body_id=1,
        head_id=1,
        hp=100,
        max_hp=100,
        level=1,
        is_hostile=True,
        is_attackable=True,
        movement_type="static",
        respawn_time=30,
        respawn_time_max=60,
        gold_min=10,
        gold_max=50,
    )

    npc2 = NPC(
        npc_id=2,
        char_index=10002,
        instance_id="npc_002",
        map_id=1,
        x=50,  # ← Misma posición que npc1
        y=50,  # ← Misma posición que npc1
        heading=3,
        name="Lobo",
        description="Un lobo salvaje",
        body_id=2,
        head_id=2,
        hp=80,
        max_hp=80,
        level=2,
        is_hostile=True,
        is_attackable=True,
        movement_type="random",
        respawn_time=30,
        respawn_time_max=60,
        gold_min=20,
        gold_max=60,
    )

    # Agregar primer NPC
    map_manager.add_npc(npc1.map_id, npc1)

    # Intentar agregar segundo NPC en la misma posición debe lanzar ValueError
    with pytest.raises(ValueError, match="tile ya ocupado"):
        map_manager.add_npc(npc2.map_id, npc2)


def test_player_cannot_move_to_npc_position(map_manager, sample_npc):
    """Verifica que un jugador no puede moverse a un tile ocupado por un NPC."""
    # Agregar NPC en (50, 50)
    map_manager.add_npc(sample_npc.map_id, sample_npc)

    # Verificar que el tile está ocupado por el NPC
    assert not map_manager.can_move_to(1, 50, 50)

    # Verificar que is_tile_occupied retorna True
    assert map_manager.is_tile_occupied(1, 50, 50)

    # Verificar que el ocupante es el NPC
    occupant = map_manager.get_tile_occupant(1, 50, 50)
    assert occupant == f"npc:{sample_npc.instance_id}"


def test_tile_occupation_after_npc_death_and_gold_drop(map_manager, sample_npc):
    """Simula el flujo completo: NPC muere, dropea oro, jugador recoge.

    Este es el caso de uso real que causaba el bug:
    1. NPC está en (50, 50) - tile bloqueado
    2. NPC muere y se remueve - tile debe quedar libre
    3. Oro se dropea en (50, 50) - tile debe seguir libre
    4. Jugador debe poder moverse a (50, 50) para recoger el oro
    """
    # 1. NPC está vivo en (50, 50)
    map_manager.add_npc(sample_npc.map_id, sample_npc)
    assert not map_manager.can_move_to(1, 50, 50)  # Bloqueado por NPC

    # 2. NPC muere y se remueve
    map_manager.remove_npc(sample_npc.map_id, sample_npc.instance_id)

    # 3. Verificar que el tile quedó libre (oro se dropea aquí)
    assert map_manager.can_move_to(1, 50, 50)  # ✅ Libre para moverse

    # 4. Agregar oro al tile (simulado con ground_items)
    gold_item = {
        "item_id": 12,  # GOLD_ITEM_ID
        "quantity": 100,
        "grh_index": 511,
        "owner_id": None,
        "spawn_time": None,
    }
    map_manager.add_ground_item(map_id=1, x=50, y=50, item=gold_item)

    # 5. Verificar que el tile SIGUE libre (items en el suelo no bloquean)
    assert map_manager.can_move_to(1, 50, 50)  # ✅ Libre para recoger oro
