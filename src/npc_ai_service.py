"""Servicio de IA para NPCs hostiles."""

import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.combat_service import CombatService
    from src.map_manager import MapManager
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.npc import NPC
    from src.npc_service import NPCService
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class NPCAIService:
    """Servicio que maneja la IA de NPCs hostiles."""

    def __init__(
        self,
        npc_service: NPCService,
        map_manager: MapManager,
        player_repo: PlayerRepository,
        combat_service: CombatService,
        broadcast_service: MultiplayerBroadcastService,
    ) -> None:
        """Inicializa el servicio de IA.

        Args:
            npc_service: Servicio de NPCs.
            map_manager: Gestor de mapas.
            player_repo: Repositorio de jugadores.
            combat_service: Servicio de combate.
            broadcast_service: Servicio de broadcast.
        """
        self.npc_service = npc_service
        self.map_manager = map_manager
        self.player_repo = player_repo
        self.combat_service = combat_service
        self.broadcast_service = broadcast_service

    async def find_nearest_player(
        self, npc: NPC, max_range: int = 8
    ) -> tuple[int, int, int] | None:
        """Encuentra el jugador más cercano al NPC.

        Args:
            npc: NPC que busca jugadores.
            max_range: Rango máximo de detección.

        Returns:
            Tupla (user_id, x, y) del jugador más cercano, o None si no hay ninguno.
        """
        # Obtener todos los jugadores en el mapa
        user_ids = self.map_manager.get_players_in_map(npc.map_id)

        if not user_ids:
            return None

        nearest_player = None
        min_distance = float("inf")

        for user_id in user_ids:
            # Obtener posición del jugador
            player_pos = await self.player_repo.get_position(user_id)
            if not player_pos or player_pos["map"] != npc.map_id:
                continue

            px, py = player_pos["x"], player_pos["y"]

            # Calcular distancia Manhattan
            distance = abs(npc.x - px) + abs(npc.y - py)

            if distance <= max_range and distance < min_distance:
                min_distance = distance
                nearest_player = (user_id, px, py)

        return nearest_player

    def get_direction_to_target(  # noqa: PLR6301
        self, from_x: int, from_y: int, to_x: int, to_y: int
    ) -> int:
        """Calcula la dirección hacia un objetivo.

        Args:
            from_x: Posición X origen.
            from_y: Posición Y origen.
            to_x: Posición X destino.
            to_y: Posición Y destino.

        Returns:
            Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste).
        """
        dx = to_x - from_x
        dy = to_y - from_y

        # Priorizar movimiento horizontal o vertical según cuál sea mayor
        if abs(dx) > abs(dy):
            # Movimiento horizontal
            return 2 if dx > 0 else 4  # Este o Oeste
        # Movimiento vertical
        return 3 if dy > 0 else 1  # Sur o Norte

    async def try_attack_player(self, npc: NPC, target_user_id: int) -> bool:
        """Intenta que el NPC ataque a un jugador.

        Args:
            npc: NPC que ataca.
            target_user_id: ID del jugador objetivo.

        Returns:
            True si atacó exitosamente.
        """
        # Obtener posición del jugador
        target_pos = await self.player_repo.get_position(target_user_id)
        if not target_pos:
            return False

        # Verificar que están en el mismo mapa
        if target_pos["map"] != npc.map_id:
            return False

        # Verificar que están adyacentes (rango de ataque = 1)
        dx = abs(npc.x - target_pos["x"])
        dy = abs(npc.y - target_pos["y"])

        if dx + dy != 1:  # No están adyacentes
            return False

        # Realizar ataque NPC -> Jugador
        result = await self.combat_service.npc_attack_player(npc, target_user_id)

        if result and result.get("damage", 0) > 0:
            logger.info(
                "NPC %s atacó a jugador %d por %d de daño",
                npc.name,
                target_user_id,
                result["damage"],
            )
            return True

        return False

    async def try_move_towards(self, npc: NPC, target_x: int, target_y: int) -> bool:
        """Intenta mover el NPC hacia una posición objetivo.

        Args:
            npc: NPC a mover.
            target_x: Coordenada X objetivo.
            target_y: Coordenada Y objetivo.

        Returns:
            True si se movió exitosamente.
        """
        # Calcular dirección hacia el objetivo
        direction = self.get_direction_to_target(npc.x, npc.y, target_x, target_y)

        # Calcular nueva posición según dirección
        new_x, new_y = npc.x, npc.y

        if direction == 1:  # Norte
            new_y -= 1
        elif direction == 2:  # Este  # noqa: PLR2004
            new_x += 1
        elif direction == 3:  # Sur  # noqa: PLR2004
            new_y += 1
        elif direction == 4:  # Oeste  # noqa: PLR2004
            new_x -= 1

        # Verificar que la nueva posición es válida
        if not self.map_manager.can_move_to(npc.map_id, new_x, new_y):
            return False

        # Verificar que no esté ocupada
        if self.map_manager.is_tile_occupied(npc.map_id, new_x, new_y):
            return False

        # Mover el NPC
        old_x, old_y = npc.x, npc.y
        npc.x = new_x
        npc.y = new_y
        npc.heading = direction

        # Actualizar en MapManager
        self.map_manager.move_npc(npc.map_id, npc.char_index, old_x, old_y, new_x, new_y)

        # Broadcast CHARACTER_MOVE
        await self.broadcast_service.broadcast_character_move(
            map_id=npc.map_id,
            char_index=npc.char_index,
            new_x=new_x,
            new_y=new_y,
            new_heading=direction,
            old_x=old_x,
            old_y=old_y,
        )

        logger.debug(
            "NPC %s se movió de (%d,%d) a (%d,%d) persiguiendo objetivo",
            npc.name,
            old_x,
            old_y,
            new_x,
            new_y,
        )

        return True

    async def process_hostile_npc(self, npc: NPC) -> None:
        """Procesa el comportamiento de un NPC hostil.

        Args:
            npc: NPC a procesar.
        """
        if not npc.is_hostile:
            return

        # Buscar jugador más cercano
        nearest = await self.find_nearest_player(npc, max_range=8)

        if not nearest:
            # No hay jugadores cerca, comportamiento idle
            # Podríamos agregar movimiento aleatorio aquí
            return

        target_user_id, target_x, target_y = nearest

        # Calcular distancia al jugador
        distance = abs(npc.x - target_x) + abs(npc.y - target_y)

        # Si está adyacente, atacar
        if distance == 1:
            await self.try_attack_player(npc, target_user_id)
        # Si está cerca pero no adyacente, perseguir
        elif distance <= 8 and random.random() < 0.5:  # noqa: PLR2004, S311
            # 50% de probabilidad de moverse (para no ser demasiado agresivo)
            await self.try_move_towards(npc, target_x, target_y)
