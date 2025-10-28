"""Tests para NPCSpawnService."""

import sys
from pathlib import Path

# Agregar src al path para poder importar servicios
sys.path.append(str(Path(__file__).parent.parent / "src"))

from services.game.npc_spawn_service import NPCSpawnService


class TestNPCSpawnService:
    """Tests para NPCSpawnService."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.service = NPCSpawnService()

    def test_service_initialization(self) -> None:
        """Test inicialización del servicio."""
        assert self.service is not None
        assert hasattr(self.service, "map_npcs")
        assert hasattr(self.service, "spawned_npcs")
        assert len(self.service.map_npcs) >= 1  # Debe tener defaults

    def test_load_map_npcs(self) -> None:
        """Test carga de NPCs por mapa."""
        # El servicio debe tener configuración por defecto
        assert 1 in self.service.map_npcs  # Ullathorpe
        assert 34 in self.service.map_npcs  # Nix

        # Verificar estructura de configuración
        ulla_config = self.service.map_npcs[1]
        assert "spawn_points" in ulla_config
        assert len(ulla_config["spawn_points"]) >= 2

    def test_spawn_npcs_for_player(self) -> None:
        """Test spawning de NPCs para jugador."""
        # Spawnear NPCs en Ullathorpe (mapa 1)
        spawned = self.service.spawn_npcs_for_player(1, 50, 50)

        assert isinstance(spawned, list)
        assert len(spawned) >= 1  # Al menos los NPCs disponibles

        # Verificar estructura de NPCs spawneados
        for npc in spawned:
            assert "id" in npc
            assert "name" in npc
            assert "map" in npc
            assert "x" in npc
            assert "y" in npc
            assert "instance_id" in npc
            assert npc["map"] == 1

    def test_vision_range_filtering(self) -> None:
        """Test filtrado por rango de visión."""
        # Jugador lejos de spawn points
        spawned_far = self.service.spawn_npcs_for_player(1, 1, 1)

        # Jugador cerca de spawn points
        spawned_near = self.service.spawn_npcs_for_player(1, 50, 50)

        # Deberían spawnear más NPCs cuando está cerca
        assert len(spawned_near) > len(spawned_far)

    def test_is_in_vision_range(self) -> None:
        """Test verificación de rango de visión."""
        # Dentro del rango
        assert self.service._is_in_vision_range(50, 50, 55, 55)
        assert self.service._is_in_vision_range(50, 50, 45, 45)

        # Fuera del rango
        assert not self.service._is_in_vision_range(50, 50, 100, 100)
        assert not self.service._is_in_vision_range(1, 1, 50, 50)

    def test_get_npc_at_position(self) -> None:
        """Test obtención de NPC en posición específica."""
        # Spawnear NPCs primero
        spawned = self.service.spawn_npcs_for_player(1, 50, 50)

        if spawned:
            # Buscar NPC en posición de spawn
            npc = spawned[0]
            found_npc = self.service.get_npc_at_position(1, npc["x"], npc["y"])

            assert found_npc is not None
            assert found_npc["x"] == npc["x"]
            assert found_npc["y"] == npc["y"]

    def test_update_npc_position(self) -> None:
        """Test actualización de posición de NPC."""
        # Spawnear NPC primero
        spawned = self.service.spawn_npcs_for_player(1, 50, 50)

        if spawned:
            npc = spawned[0]
            instance_id = npc["instance_id"]

            # Actualizar posición
            success = self.service.update_npc_position(instance_id, 51, 51, 2)
            assert success

            # Verificar nueva posición
            updated_npc = self.service.spawned_npcs[instance_id]
            assert updated_npc["x"] == 51
            assert updated_npc["y"] == 51
            assert updated_npc["direction"] == 2

    def test_despawn_npc(self) -> None:
        """Test despawn de NPC."""
        # Spawnear NPC primero
        spawned = self.service.spawn_npcs_for_player(1, 50, 50)

        if spawned:
            npc = spawned[0]
            instance_id = npc["instance_id"]

            # Verificar que existe
            assert instance_id in self.service.spawned_npcs

            # Despawnear
            success = self.service.despawn_npc(instance_id)
            assert success

            # Verificar que fue eliminado
            assert instance_id not in self.service.spawned_npcs

    def test_despawn_npcs_out_of_range(self) -> None:
        """Test despawn de NPCs fuera de rango."""
        # Spawnear NPCs cerca
        spawned_near = self.service.spawn_npcs_for_player(1, 50, 50)
        initial_count = len(spawned_near)

        # Mover jugador lejos y despawnear fuera de rango
        despawned = self.service.despawn_npcs_out_of_range(1, 1, 1)

        assert len(despawned) > 0
        assert len(self.service.spawned_npcs) < initial_count

    def test_get_all_spawned_npcs(self) -> None:
        """Test obtención de todos los NPCs spawneados."""
        # Debe estar vacío inicialmente
        assert len(self.service.get_all_spawned_npcs()) == 0

        # Spawnear NPCs
        self.service.spawn_npcs_for_player(1, 50, 50)

        # Ahora debe tener NPCs
        all_npcs = self.service.get_all_spawned_npcs()
        assert len(all_npcs) > 0

        # Verificar que es una copia (no referencia directa)
        all_npcs["test"] = {}
        assert "test" not in self.service.spawned_npcs

    def test_get_npcs_in_map(self) -> None:
        """Test obtención de NPCs por mapa."""
        # Spawnear en mapa 1
        self.service.spawn_npcs_for_player(1, 50, 50)

        # Spawnear en mapa 34
        self.service.spawn_npcs_for_player(34, 30, 30)

        npcs_map_1 = self.service.get_npcs_in_map(1)
        npcs_map_34 = self.service.get_npcs_in_map(34)
        npcs_map_99 = self.service.get_npcs_in_map(99)  # No existe

        assert len(npcs_map_1) > 0
        assert len(npcs_map_34) > 0
        assert len(npcs_map_99) == 0

        # Verificar que están en el mapa correcto
        for npc in npcs_map_1:
            assert npc["map"] == 1

        for npc in npcs_map_34:
            assert npc["map"] == 34

    def test_get_spawn_statistics(self) -> None:
        """Test obtención de estadísticas de spawn."""
        stats = self.service.get_spawn_statistics()

        assert "total_spawned" in stats
        assert "npcs_by_map" in stats
        assert "hostile_count" in stats
        assert "trader_count" in stats
        assert "configured_maps" in stats

        assert isinstance(stats["total_spawned"], int)
        assert isinstance(stats["npcs_by_map"], dict)
        assert isinstance(stats["configured_maps"], int)
        assert stats["configured_maps"] >= 2

    def test_random_spawn_generation(self) -> None:
        """Test generación de spawns aleatorios."""
        # Forzar spawns aleatorios en área designada
        spawned = self.service.spawn_npcs_for_player(1, 80, 80)  # Cerca del área aleatoria

        # Puede o no haber spawns aleatorios (probabilidad)
        # Pero no debe fallar
        assert isinstance(spawned, list)

        # Verificar spawns aleatorios si existen
        random_npcs = [npc for npc in spawned if npc.get("random_spawn")]

        for npc in random_npcs:
            assert "random_spawn" in npc
            assert npc["random_spawn"] is True
            assert 70 <= npc["x"] <= 90  # Dentro del área configurada
            assert 70 <= npc["y"] <= 90

    def test_error_handling(self) -> None:
        """Test manejo de errores."""
        # Posición inválida
        npc = self.service.get_npc_at_position(999, 999, 999)
        assert npc is None

        # Actualizar NPC inexistente
        success = self.service.update_npc_position("invalid_id", 1, 1, 1)
        assert not success

        # Despawnear NPC inexistente
        success = self.service.despawn_npc("invalid_id")
        assert success  # No lanza error, simplemente no hace nada


class TestNPCSpawnServiceIntegration:
    """Tests de integración para NPCSpawnService."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.service = NPCSpawnService()

    def test_full_spawn_lifecycle(self) -> None:
        """Test ciclo completo de vida de un NPC."""
        player_map, player_x, player_y = 1, 50, 50

        # 1. Spawnear NPCs
        spawned = self.service.spawn_npcs_for_player(player_map, player_x, player_y)
        assert len(spawned) > 0

        npc = spawned[0]
        instance_id = npc["instance_id"]

        # 2. Encontrar NPC por posición
        found_npc = self.service.get_npc_at_position(npc["map"], npc["x"], npc["y"])
        assert found_npc is not None
        assert found_npc["instance_id"] == instance_id

        # 3. Mover NPC
        new_x, new_y = npc["x"] + 1, npc["y"] + 1
        success = self.service.update_npc_position(instance_id, new_x, new_y, 2)
        assert success

        # 4. Verificar nueva posición
        updated_npc = self.service.get_npc_at_position(npc["map"], new_x, new_y)
        assert updated_npc is not None
        assert updated_npc["instance_id"] == instance_id

        # 5. Despawnear
        success = self.service.despawn_npc(instance_id)
        assert success

        # 6. Verificar que ya no existe
        final_npc = self.service.get_npc_at_position(npc["map"], new_x, new_y)
        assert final_npc is None

    def test_multiple_players_different_maps(self) -> None:
        """Test múltiples jugadores en diferentes mapas."""
        # Jugador 1 en mapa 1
        spawned_1 = self.service.spawn_npcs_for_player(1, 50, 50)

        # Jugador 2 en mapa 34
        spawned_2 = self.service.spawn_npcs_for_player(34, 30, 30)

        # Jugador 3 en mapa 1 pero lejos
        spawned_3 = self.service.spawn_npcs_for_player(1, 1, 1)

        assert len(spawned_1) > 0
        assert len(spawned_2) > 0
        assert len(spawned_3) < len(spawned_1)  # Menos por distancia

        # Verificar que hay NPCs en ambos mapas
        total_spawned = len(self.service.get_all_spawned_npcs())
        assert total_spawned > 0

        npcs_map_1 = self.service.get_npcs_in_map(1)
        npcs_map_34 = self.service.get_npcs_in_map(34)

        assert len(npcs_map_1) > 0
        assert len(npcs_map_34) > 0

    def test_statistics_accuracy(self) -> None:
        """Test precisión de estadísticas."""
        initial_stats = self.service.get_spawn_statistics()

        # Spawnear varios NPCs
        self.service.spawn_npcs_for_player(1, 50, 50)
        self.service.spawn_npcs_for_player(34, 30, 30)

        final_stats = self.service.get_spawn_statistics()

        # Debe haber más NPCs spawneados
        assert final_stats["total_spawned"] > initial_stats["total_spawned"]

        # Debe haber NPCs en múltiples mapas
        assert len(final_stats["npcs_by_map"]) >= 2

        # Total debe coincidir
        total_manual = sum(final_stats["npcs_by_map"].values())
        assert total_manual == final_stats["total_spawned"]
