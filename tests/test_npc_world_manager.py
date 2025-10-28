"""Tests para NPCWorldManager."""

import sys
from pathlib import Path

# Agregar src al path para poder importar servicios
sys.path.append(str(Path(__file__).parent.parent / "src"))

from services.game.npc_world_manager import NPCWorldManager


class TestNPCWorldManager:
    """Tests para NPCWorldManager."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.manager = NPCWorldManager()

    def test_manager_initialization(self) -> None:
        """Test inicialización del gestor."""
        assert self.manager is not None
        assert self.manager.spawn_service is not None
        assert self.manager.npc_service is not None
        assert isinstance(self.manager.active_combats, dict)

    def test_update_player_npcs(self) -> None:
        """Test actualización de NPCs para jugador."""
        result = self.manager.update_player_npcs("test_player", 1, 50, 50)

        assert "player_id" in result
        assert "player_map" in result
        assert "spawned" in result
        assert "despawned" in result
        assert "total_visible" in result

        assert result["player_id"] == "test_player"
        assert result["player_map"] == 1
        assert isinstance(result["spawned"], list)
        assert isinstance(result["despawned"], list)
        assert isinstance(result["total_visible"], int)

        # Debe spawnear NPCs
        assert len(result["spawned"]) > 0
        assert result["total_visible"] > 0

    def test_get_npc_interaction(self) -> None:
        """Test obtención de datos de interacción."""
        # Spawnear NPC primero
        spawn_result = self.manager.update_player_npcs("test_player", 1, 50, 50)

        if spawn_result["spawned"]:
            npc = spawn_result["spawned"][0]
            instance_id = npc["instance_id"]

            # Obtener interacción
            interaction = self.manager.get_npc_interaction(instance_id)

            assert "error" not in interaction
            assert "instance_id" in interaction
            assert "npc" in interaction
            assert "template" in interaction
            assert "can_trade" in interaction
            assert "is_hostile" in interaction
            assert "dialog" in interaction
            assert "inventory" in interaction
            assert "drops" in interaction
            assert "combat_stats" in interaction
            assert "in_combat" in interaction

            assert interaction["instance_id"] == instance_id
            assert isinstance(interaction["can_trade"], bool)
            assert isinstance(interaction["is_hostile"], bool)

    def test_get_npc_interaction_invalid(self) -> None:
        """Test interacción con NPC inexistente."""
        interaction = self.manager.get_npc_interaction("invalid_npc_id")

        assert "error" in interaction
        assert interaction["error"] == "NPC no encontrado"

    def test_start_npc_combat(self) -> None:
        """Test inicio de combate con NPC."""
        # Spawnear NPC hostil
        spawn_result = self.manager.update_player_npcs("test_player", 1, 80, 80)

        # Buscar NPC hostil
        hostile_npc = None
        for npc in spawn_result["spawned"]:
            if npc.get("hostile"):
                hostile_npc = npc
                break

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]

            # Iniciar combate
            result = self.manager.start_npc_combat(instance_id, "test_player")

            assert "success" in result
            assert result["success"] is True
            assert "combat_started" in result
            assert result["combat_started"] is True
            assert result["instance_id"] == instance_id
            assert result["player_id"] == "test_player"

            # NPC debe estar en combate
            assert instance_id in self.manager.active_combats

    def test_start_npc_combat_non_hostile(self) -> None:
        """Test intento de combate con NPC no hostil."""
        spawn_result = self.manager.update_player_npcs("test_player", 1, 50, 50)

        if spawn_result["spawned"]:
            # Buscar NPC no hostil
            peaceful_npc = None
            for npc in spawn_result["spawned"]:
                if not npc.get("hostile"):
                    peaceful_npc = npc
                    break

            if peaceful_npc:
                instance_id = peaceful_npc["instance_id"]

                result = self.manager.start_npc_combat(instance_id, "test_player")

                assert "error" in result
                assert "no es hostil" in result["error"]

    def test_start_npc_combat_already_in_combat(self) -> None:
        """Test inicio de combate con NPC ya en combate."""
        spawn_result = self.manager.update_player_npcs("test_player", 1, 80, 80)

        # Buscar NPC hostil
        hostile_npc = None
        for npc in spawn_result["spawned"]:
            if npc.get("hostile"):
                hostile_npc = npc
                break

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]

            # Primer combate
            self.manager.start_npc_combat(instance_id, "test_player")

            # Intentar segundo combate
            result = self.manager.start_npc_combat(instance_id, "another_player")

            assert "error" in result
            assert "ya en combate" in result["error"]

    def test_end_npc_combat_player_wins(self) -> None:
        """Test fin de combate donde gana el jugador."""
        # Iniciar combate primero
        spawn_result = self.manager.update_player_npcs("test_player", 1, 80, 80)

        hostile_npc = next((npc for npc in spawn_result["spawned"] if npc.get("hostile")), None)

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]
            self.manager.start_npc_combat(instance_id, "test_player")

            # Terminar combate con victoria del jugador
            result = self.manager.end_npc_combat(instance_id, "player")

            assert result["success"] is True
            assert result["combat_ended"] is True
            assert result["winner"] == "player"
            assert result["npc_despawned"] is True

            # NPC no debe estar en combate ni spawneado
            assert instance_id not in self.manager.active_combats
            assert instance_id not in self.manager.spawn_service.spawned_npcs

    def test_end_npc_combat_npc_wins(self) -> None:
        """Test fin de combate donde gana el NPC."""
        spawn_result = self.manager.update_player_npcs("test_player", 1, 80, 80)

        hostile_npc = next((npc for npc in spawn_result["spawned"] if npc.get("hostile")), None)

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]
            self.manager.start_npc_combat(instance_id, "test_player")

            # Terminar combate con victoria del NPC
            result = self.manager.end_npc_combat(instance_id, "npc")

            assert result["success"] is True
            assert result["combat_ended"] is True
            assert result["winner"] == "npc"
            assert result["npc_despawned"] is False

            # NPC no debe estar en combate pero sigue spawneado
            assert instance_id not in self.manager.active_combats
            assert instance_id in self.manager.spawn_service.spawned_npcs

    def test_move_npc_randomly(self) -> None:
        """Test movimiento aleatorio de NPC."""
        spawn_result = self.manager.update_player_npcs("test_player", 1, 50, 50)

        if spawn_result["spawned"]:
            npc = spawn_result["spawned"][0]
            instance_id = npc["instance_id"]
            original_pos = {"x": npc["x"], "y": npc["y"]}

            # Mover NPC
            result = self.manager.move_npc_randomly(instance_id)

            if result.get("success"):
                assert "instance_id" in result
                assert "old_position" in result
                assert "new_position" in result
                assert "direction" in result

                # La posición debe haber cambiado (o stayed same si movimiento falló)
                assert result["instance_id"] == instance_id

    def test_move_npc_in_combat(self) -> None:
        """Test movimiento de NPC en combate."""
        spawn_result = self.manager.update_player_npcs("test_player", 1, 80, 80)

        hostile_npc = next((npc for npc in spawn_result["spawned"] if npc.get("hostile")), None)

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]

            # Poner en combate
            self.manager.start_npc_combat(instance_id, "test_player")

            # Intentar mover
            result = self.manager.move_npc_randomly(instance_id)

            assert "error" in result
            assert "en combate" in result["error"]

    def test_process_npc_tick(self) -> None:
        """Test procesamiento de tick de NPCs."""
        # Spawnear NPCs primero
        self.manager.update_player_npcs("test_player", 1, 50, 50)

        # Procesar tick
        stats = self.manager.process_npc_tick()

        assert "processed_npcs" in stats
        assert "moved_npcs" in stats
        assert "active_combats" in stats
        assert "total_spawned" in stats

        assert isinstance(stats["processed_npcs"], int)
        assert isinstance(stats["moved_npcs"], int)
        assert isinstance(stats["active_combats"], int)
        assert isinstance(stats["total_spawned"], int)

        assert stats["processed_npcs"] >= 0
        assert stats["total_spawned"] >= 0

    def test_get_nearby_npcs(self) -> None:
        """Test obtención de NPCs cercanos."""
        # Spawnear NPCs en posición específica
        self.manager.update_player_npcs("test_player", 1, 50, 50)

        # Buscar NPCs cercanos
        nearby = self.manager.get_nearby_npcs(1, 50, 50, radius=10)

        assert isinstance(nearby, list)

        for npc in nearby:
            assert npc["map"] == 1
            # Verificar que está dentro del radio (distancia Manhattan)
            distance = abs(npc["x"] - 50) + abs(npc["y"] - 50)
            assert distance <= 10

    def test_get_world_statistics(self) -> None:
        """Test obtención de estadísticas del mundo."""
        stats = self.manager.get_world_statistics()

        assert "spawn_statistics" in stats
        assert "active_combats" in stats
        assert "combat_details" in stats
        assert "total_npc_templates" in stats
        assert "hostile_templates" in stats
        assert "trader_templates" in stats

        # Verificar tipos
        assert isinstance(stats["active_combats"], int)
        assert isinstance(stats["combat_details"], list)
        assert isinstance(stats["total_npc_templates"], int)

        # Spawn statistics debe tener datos
        spawn_stats = stats["spawn_statistics"]
        assert "total_spawned" in spawn_stats
        assert "configured_maps" in spawn_stats

    def test_error_handling(self) -> None:
        """Test manejo de errores."""
        # Operaciones con IDs inválidos
        interaction = self.manager.get_npc_interaction("invalid_id")
        assert "error" in interaction

        combat_start = self.manager.start_npc_combat("invalid_id", "player")
        assert "error" in combat_start

        combat_end = self.manager.end_npc_combat("invalid_id", "player")
        assert "error" in combat_end

        movement = self.manager.move_npc_randomly("invalid_id")
        assert "error" in movement


class TestNPCWorldManagerIntegration:
    """Tests de integración para NPCWorldManager."""

    def setup_method(self) -> None:
        """Configurar método de prueba."""
        self.manager = NPCWorldManager()

    def test_complete_combat_lifecycle(self) -> None:
        """Test ciclo completo de combate."""
        player_id = "test_player"

        # 1. Spawnear NPCs
        spawn_result = self.manager.update_player_npcs(player_id, 1, 80, 80)

        hostile_npc = next((npc for npc in spawn_result["spawned"] if npc.get("hostile")), None)

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]

            # 2. Iniciar combate
            combat_start = self.manager.start_npc_combat(instance_id, player_id)
            assert combat_start["success"] is True
            assert instance_id in self.manager.active_combats

            # 3. NPC no debe poder moverse en combate
            movement = self.manager.move_npc_randomly(instance_id)
            assert "error" in movement

            # 4. Terminar combate
            combat_end = self.manager.end_npc_combat(instance_id, "player")
            assert combat_end["success"] is True
            assert instance_id not in self.manager.active_combats

    def test_multiple_players_same_map(self) -> None:
        """Test múltiples jugadores en el mismo mapa."""
        # Jugador 1 spawnea NPCs
        result_1 = self.manager.update_player_npcs("player_1", 1, 50, 50)

        # Jugador 2 spawnea NPCs (debería ver los mismos)
        result_2 = self.manager.update_player_npcs("player_2", 1, 52, 52)

        # Ambos deberían ver NPCs similares
        assert len(result_1["spawned"]) > 0
        assert len(result_2["spawned"]) > 0

        # Estadísticas del mundo deben reflejar todos los NPCs
        world_stats = self.manager.get_world_statistics()
        assert world_stats["spawn_statistics"]["total_spawned"] > 0

    def test_tick_processing_with_combat(self) -> None:
        """Test procesamiento de tick durante combate."""
        # Iniciar combate
        spawn_result = self.manager.update_player_npcs("player", 1, 80, 80)

        hostile_npc = next((npc for npc in spawn_result["spawned"] if npc.get("hostile")), None)

        if hostile_npc:
            instance_id = hostile_npc["instance_id"]
            self.manager.start_npc_combat(instance_id, "player")

            # Procesar tick - NPCs en combate no deben moverse
            stats = self.manager.process_npc_tick()

            assert stats["active_combats"] > 0
            assert stats["processed_npcs"] > 0

    def test_world_statistics_accuracy(self) -> None:
        """Test precisión de estadísticas del mundo."""
        initial_stats = self.manager.get_world_statistics()

        # Spawnear NPCs y combates
        self.manager.update_player_npcs("player_1", 1, 50, 50)
        self.manager.update_player_npcs("player_2", 34, 30, 30)

        spawn_result = self.manager.update_player_npcs("player_3", 1, 80, 80)
        hostile_npc = next((npc for npc in spawn_result["spawned"] if npc.get("hostile")), None)

        if hostile_npc:
            self.manager.start_npc_combat(hostile_npc["instance_id"], "player_3")

        final_stats = self.manager.get_world_statistics()

        # Debe haber más actividad
        assert (
            final_stats["spawn_statistics"]["total_spawned"]
            >= initial_stats["spawn_statistics"]["total_spawned"]
        )
        assert final_stats["spawn_statistics"]["npcs_by_map"] != {}
