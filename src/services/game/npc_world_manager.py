"""Gestor de NPCs en el mundo del juego.

Coordina la interacción entre NPCs, jugadores y el sistema de juego,
manejo de estados y eventos del mundo.
"""

from __future__ import annotations

import logging
import random
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender

from .npc_service import get_npc_service
from .npc_spawn_service import get_npc_spawn_service

logger = logging.getLogger(__name__)

# Constantes
MAP_MIN_X = 1
MAP_MAX_X = 100
MAP_MIN_Y = 1
MAP_MAX_Y = 100
NPC_MOVE_CHANCE = 0.1


class NPCWorldManager:
    """Gestor principal de NPCs en el mundo del juego."""

    _instance: ClassVar[NPCWorldManager | None] = None

    def __init__(self) -> None:
        """Inicializa NPCWorldManager."""
        if getattr(self, "_initialized", False):
            return

        self.spawn_service = get_npc_spawn_service()
        self.npc_service = get_npc_service()
        self.message_sender: MessageSender | None = None
        self.active_combats: dict[str, dict[str, Any]] = {}  # npc_instance_id -> combat_data

        self._initialized = True

    @classmethod
    def get_instance(cls) -> NPCWorldManager:
        """Obtiene la instancia singleton del gestor.

        Returns:
            Instancia única del ``NPCWorldManager``.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reinicia la instancia singleton del gestor."""
        cls._instance = None

    def update_player_npcs(
        self, player_id: str, player_map: int, player_x: int, player_y: int
    ) -> dict[str, Any]:
        """Actualiza los NPCs visibles para un jugador.

        Args:
            player_id: ID del jugador.
            player_map: Mapa actual del jugador.
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.

        Returns:
            Datos con NPCs spawneados y despawneados.
        """
        # Despawnear NPCs fuera de rango
        despawned = self.spawn_service.despawn_npcs_out_of_range(player_map, player_x, player_y)

        # Spawnear NPCs en rango
        spawned_npcs = self.spawn_service.spawn_npcs_for_player(player_map, player_x, player_y)

        result = {
            "player_id": player_id,
            "player_map": player_map,
            "spawned": spawned_npcs,
            "despawned": despawned,
            "total_visible": len(spawned_npcs),
        }

        if despawned:
            logger.debug("Jugador %s: despawned %d NPCs", player_id, len(despawned))

        if spawned_npcs:
            logger.debug("Jugador %s: spawned %d NPCs", player_id, len(spawned_npcs))

        return result

    def get_npc_interaction(self, instance_id: str) -> dict[str, Any]:
        """Obtiene datos de interacción para un NPC.

        Args:
            instance_id: ID de instancia del NPC.

        Returns:
            Datos de interacción o error si no existe.
        """
        spawned_npcs = self.spawn_service.get_all_spawned_npcs()

        if instance_id not in spawned_npcs:
            return {"error": "NPC no encontrado", "instance_id": instance_id}

        npc = spawned_npcs[instance_id]
        npc_template = self.npc_service.get_npc_by_id(npc["id"])

        if not npc_template:
            return {"error": "Plantilla NPC no encontrada", "instance_id": instance_id}

        return {
            "instance_id": instance_id,
            "npc": npc,
            "template": npc_template,
            "can_trade": npc["trader"],
            "is_hostile": npc["hostile"],
            "dialog": npc_template.get("description", ""),
            "inventory": self.npc_service.get_npc_inventory(npc["id"]),
            "drops": self.npc_service.get_npc_drops(npc["id"]),
            "combat_stats": npc_template.get("combat", {}),
            "in_combat": instance_id in self.active_combats,
        }

    def start_npc_combat(self, instance_id: str, player_id: str) -> dict[str, Any]:
        """Inicia combate entre jugador y NPC.

        Args:
            instance_id: ID de instancia del NPC.
            player_id: ID del jugador.

        Returns:
            Resultado del inicio de combate.
        """
        interaction = self.get_npc_interaction(instance_id)

        if "error" in interaction:
            return interaction

        if not interaction["is_hostile"]:
            return {"error": "NPC no es hostil", "instance_id": instance_id}

        if interaction["in_combat"]:
            return {"error": "NPC ya en combate", "instance_id": instance_id}

        combat_data = {
            "instance_id": instance_id,
            "player_id": player_id,
            "start_time": None,  # TODO: Usar timestamp real
            "original_position": {
                "map": interaction["npc"]["map"],
                "x": interaction["npc"]["x"],
                "y": interaction["npc"]["y"],
            },
            "target_player": player_id,
        }

        self.active_combats[instance_id] = combat_data

        return {
            "success": True,
            "combat_started": True,
            "instance_id": instance_id,
            "player_id": player_id,
            "npc_stats": interaction["combat_stats"],
        }

    def end_npc_combat(self, instance_id: str, winner: str) -> dict[str, Any]:
        """Finaliza combate entre jugador y NPC.

        Args:
            instance_id: ID de instancia del NPC.
            winner: Ganador del combate ("player" o "npc").

        Returns:
            Resultado del fin de combate.
        """
        if instance_id not in self.active_combats:
            return {"error": "NPC no en combate", "instance_id": instance_id}

        # Eliminar NPC si el jugador ganó
        despawned = False
        if winner == "player":
            despawned = self.spawn_service.despawn_npc(instance_id)

        # Limpiar datos de combate
        del self.active_combats[instance_id]

        result = {
            "success": True,
            "combat_ended": True,
            "instance_id": instance_id,
            "winner": winner,
            "npc_despawned": despawned,
        }

        logger.info("Combate terminado: %s, ganador: %s", instance_id, winner)

        return result

    def move_npc_randomly(self, instance_id: str) -> dict[str, Any]:
        """Mueve un NPC aleatoriamente en su área.

        Args:
            instance_id: ID de instancia del NPC.

        Returns:
            Nueva posición del NPC o error.
        """
        spawned_npcs = self.spawn_service.get_all_spawned_npcs()

        if instance_id not in spawned_npcs:
            return {"error": "NPC no encontrado", "instance_id": instance_id}

        npc = spawned_npcs[instance_id]

        # NPCs en combate no se mueven aleatoriamente
        if instance_id in self.active_combats:
            return {"error": "NPC en combate", "instance_id": instance_id}

        # Movimiento aleatorio simple
        directions = [(0, 1, 2), (0, -1, 4), (1, 0, 1), (-1, 0, 3)]  # dx, dy, direction
        dx, dy, direction = random.choice(directions)

        new_x = npc["x"] + dx
        new_y = npc["y"] + dy

        # Verificar límites del mapa (simple)
        if new_x < MAP_MIN_X or new_x > MAP_MAX_X or new_y < MAP_MIN_Y or new_y > MAP_MAX_Y:
            return {"error": "Movimiento fuera de límites", "instance_id": instance_id}

        # Actualizar posición
        if self.spawn_service.update_npc_position(instance_id, new_x, new_y, direction):
            return {
                "success": True,
                "instance_id": instance_id,
                "old_position": {"x": npc["x"], "y": npc["y"]},
                "new_position": {"x": new_x, "y": new_y},
                "direction": direction,
            }

        return {"error": "Error actualizando posición", "instance_id": instance_id}

    def process_npc_tick(self) -> dict[str, Any]:
        """Procesa un tick de juego para todos los NPCs activos.

        Returns:
            Estadísticas del tick procesado.
        """
        processed_npcs = 0
        moved_npcs = 0
        combat_checks = 0

        spawned_npcs = self.spawn_service.get_all_spawned_npcs()

        for instance_id in spawned_npcs:
            processed_npcs += 1

            # NPCs en combate no procesan comportamiento normal
            if instance_id in self.active_combats:
                combat_checks += 1
                continue

            # Movimiento aleatorio (NPC_MOVE_CHANCE de probabilidad)
            if random.random() < NPC_MOVE_CHANCE:  # chance de moverse
                move_result = self.move_npc_randomly(instance_id)
                if move_result.get("success"):
                    moved_npcs += 1

        stats = {
            "processed_npcs": processed_npcs,
            "moved_npcs": moved_npcs,
            "active_combats": combat_checks,
            "total_spawned": len(spawned_npcs),
        }

        logger.debug("NPC tick procesado: %s", stats)

        return stats

    def get_nearby_npcs(
        self, map_num: int, x: int, y: int, radius: int = 5
    ) -> list[dict[str, Any]]:
        """Obtiene NPCs cercanos a una posición.

        Args:
            map_num: Número del mapa.
            x: Posición X.
            y: Posición Y.
            radius: Radio de búsqueda.

        Returns:
            Lista de NPCs cercanos.
        """
        nearby = []
        spawned_npcs = self.spawn_service.get_all_spawned_npcs()

        for npc in spawned_npcs.values():
            if npc["map"] != map_num:
                continue

            distance = abs(npc["x"] - x) + abs(npc["y"] - y)
            if distance <= radius:
                nearby.append(npc)

        return nearby

    def get_world_statistics(self) -> dict[str, Any]:
        """Retorna estadísticas del mundo de NPCs.

        Returns:
            Estadísticas completas del sistema.
        """
        spawn_stats = self.spawn_service.get_spawn_statistics()

        return {
            "spawn_statistics": spawn_stats,
            "active_combats": len(self.active_combats),
            "combat_details": list(self.active_combats.keys()),
            "total_npc_templates": len(self.npc_service.get_all_npcs()),
            "hostile_templates": len(self.npc_service.get_hostile_npcs()),
            "trader_templates": len(self.npc_service.get_trader_npcs()),
        }


def get_npc_world_manager() -> NPCWorldManager:
    """Obtiene la instancia singleton del gestor de NPCs del mundo.

    Returns:
        Instancia única del ``NPCWorldManager``.
    """
    return NPCWorldManager.get_instance()


def initialize_npc_world_manager() -> NPCWorldManager:
    """Reinicia y retorna la instancia singleton del gestor de NPCs.

    Returns:
        Instancia única del ``NPCWorldManager`` reinicializada.
    """
    NPCWorldManager.reset_instance()
    return NPCWorldManager.get_instance()
