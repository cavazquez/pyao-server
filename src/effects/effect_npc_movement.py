"""Efecto de movimiento aleatorio de NPCs."""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)


class NPCMovementEffect(TickEffect):
    """Efecto que hace que los NPCs se muevan aleatoriamente."""

    def __init__(self, npc_service: NPCService, interval_seconds: float = 5.0) -> None:
        """Inicializa el efecto de movimiento de NPCs.

        Args:
            npc_service: Servicio de NPCs.
            interval_seconds: Intervalo entre movimientos en segundos.
        """
        self.npc_service = npc_service
        self.interval_seconds = interval_seconds
        self._already_executed_this_tick = False
        self._player_repo: PlayerRepository | None = None

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto para logging.

        Returns:
            Nombre del efecto.
        """
        return "NPCMovement"

    async def apply(
        self,
        user_id: int,  # noqa: ARG002
        player_repo: PlayerRepository,
        message_sender: MessageSender | None,  # noqa: ARG002
    ) -> None:
        """Aplica el efecto de movimiento aleatorio a los NPCs.

        Nota: Este efecto ignora los parámetros de jugador ya que opera sobre NPCs globalmente.
        Solo se ejecuta una vez por tick, no por cada jugador.

        Args:
            user_id: ID del usuario (ignorado).
            player_repo: Repositorio de jugadores (ignorado).
            message_sender: MessageSender del jugador (ignorado).
        """
        # Guardar player_repo para uso posterior
        if self._player_repo is None:
            self._player_repo = player_repo

        # Solo ejecutar una vez por tick, no por cada jugador
        if self._already_executed_this_tick:
            return

        self._already_executed_this_tick = True

        # Resetear el flag después de un breve delay para el próximo tick
        self._reset_task = asyncio.create_task(self._reset_execution_flag())
        # Obtener todos los NPCs del mundo
        all_npcs = self.npc_service.map_manager.get_all_npcs()

        if not all_npcs:
            logger.debug("No hay NPCs en el mundo para mover")
            return

        logger.debug("Moviendo NPCs: %d NPCs totales en el mundo", len(all_npcs))

        # Mover algunos NPCs aleatoriamente (no todos a la vez)
        npcs_to_move = random.sample(all_npcs, min(len(all_npcs), max(1, len(all_npcs) // 3)))

        for npc in npcs_to_move:
            # Solo mover NPCs hostiles (lobos, goblins, etc.)
            # Los NPCs amigables (comerciantes, banqueros) no se mueven
            if npc.npc_id in {1, 7}:  # Goblin=1, Lobo=7
                await self._move_npc_with_ai(npc, self._player_repo)

    async def _move_npc_with_ai(self, npc: NPC, player_repo: PlayerRepository | None) -> None:
        """Mueve un NPC con IA: persigue jugadores cercanos o se mueve aleatoriamente.

        Args:
            npc: Instancia del NPC a mover.
            player_repo: Repositorio de jugadores para obtener posiciones.
        """
        # Si no tenemos player_repo, solo moverse aleatoriamente
        if player_repo is None:
            logger.debug("NPC %s - No hay player_repo disponible, movimiento aleatorio", npc.name)
            await self._move_npc_randomly(npc)
            return

        # Buscar jugadores cercanos en el mismo mapa
        # Obtener todos los user_ids en el mapa
        player_ids = self.npc_service.map_manager.get_players_in_map(npc.map_id)

        logger.debug(
            "NPC %s en mapa %d buscando jugadores - %d jugadores en el mapa",
            npc.name,
            npc.map_id,
            len(player_ids),
        )

        closest_player = None
        min_distance = float("inf")

        # Encontrar el jugador más cercano dentro del rango de detección (10 tiles)
        for user_id in player_ids:
            logger.debug("Procesando jugador user_id: %d", user_id)

            # Obtener posición del jugador desde Redis
            try:
                position = await player_repo.get_position(user_id)
                if not position:
                    logger.debug("No se pudo obtener posición para user_id %d", user_id)
                    continue

                player_x = position.get("x", 0)
                player_y = position.get("y", 0)

                # Calcular distancia Manhattan
                distance = abs(npc.x - player_x) + abs(npc.y - player_y)

                logger.debug(
                    "Jugador %d en (%d,%d) - NPC %s en (%d,%d) - distancia=%d",
                    user_id,
                    player_x,
                    player_y,
                    npc.name,
                    npc.x,
                    npc.y,
                    distance,
                )

                if distance < min_distance and distance <= 10:  # noqa: PLR2004
                    min_distance = distance
                    closest_player = (player_x, player_y)
            except Exception:  # noqa: BLE001
                logger.debug("Error obteniendo posición de user_id %d", user_id)
                continue

        # Si hay un jugador cercano, moverse hacia él
        if closest_player:
            target_x, target_y = closest_player
            logger.debug(
                "NPC %s (ID:%d) detectó jugador en (%d,%d), distancia=%d - PERSIGUIENDO",
                npc.name,
                npc.npc_id,
                target_x,
                target_y,
                min_distance,
            )
            await self._move_towards_target(npc, target_x, target_y)
        else:
            # Si no hay jugadores cerca, moverse aleatoriamente
            logger.debug(
                "NPC %s (ID:%d) no detectó jugadores - movimiento aleatorio", npc.name, npc.npc_id
            )
            await self._move_npc_randomly(npc)

    async def _move_towards_target(self, npc: NPC, target_x: int, target_y: int) -> None:
        """Mueve un NPC un paso hacia un objetivo.

        Args:
            npc: Instancia del NPC a mover.
            target_x: Coordenada X del objetivo.
            target_y: Coordenada Y del objetivo.
        """
        # Calcular diferencias
        dx = target_x - npc.x
        dy = target_y - npc.y

        # Decidir dirección prioritaria (la que tiene mayor diferencia)
        new_x = npc.x
        new_y = npc.y
        new_heading = npc.heading

        if abs(dx) > abs(dy):
            # Moverse horizontalmente
            if dx > 0:
                new_x += 1
                new_heading = 2  # Este
            else:
                new_x -= 1
                new_heading = 4  # Oeste
        # Moverse verticalmente
        elif dy > 0:
            new_y += 1
            new_heading = 3  # Sur
        else:
            new_y -= 1
            new_heading = 1  # Norte

        # Validar colisiones con MapManager
        if not self.npc_service.map_manager.can_move_to(npc.map_id, new_x, new_y):
            return

        # Mover el NPC
        try:
            await self.npc_service.move_npc(npc, new_x, new_y, new_heading)
        except Exception:
            logger.exception("Error al mover NPC %s hacia jugador", npc.name)

    async def _move_npc_randomly(self, npc: NPC) -> None:
        """Mueve un NPC en una dirección aleatoria.

        Args:
            npc: Instancia del NPC a mover.
        """
        # Elegir dirección aleatoria (1=Norte, 2=Este, 3=Sur, 4=Oeste)
        direction = random.randint(1, 4)  # noqa: S311

        new_x = npc.x
        new_y = npc.y
        new_heading = direction

        # Calcular nueva posición según dirección
        if direction == 1:  # Norte
            new_y -= 1
        elif direction == 2:  # Este  # noqa: PLR2004
            new_x += 1
        elif direction == 3:  # Sur  # noqa: PLR2004
            new_y += 1
        elif direction == 4:  # Oeste  # noqa: PLR2004
            new_x -= 1

        # Validar colisiones con MapManager
        if not self.npc_service.map_manager.can_move_to(npc.map_id, new_x, new_y):
            return

        # Limitar movimiento a un área cercana al spawn (radio de 5 tiles)
        spawn_x = npc.x  # Usar posición actual como referencia
        spawn_y = npc.y
        distance_from_spawn = abs(new_x - spawn_x) + abs(new_y - spawn_y)

        if distance_from_spawn > 5:  # noqa: PLR2004
            return

        # Mover el NPC
        try:
            await self.npc_service.move_npc(npc, new_x, new_y, new_heading)
        except Exception:
            logger.exception("Error al mover NPC %s", npc.name)

    async def _reset_execution_flag(self) -> None:
        """Resetea el flag de ejecución después de un breve delay."""
        # Breve delay para asegurar que todos los jugadores fueron procesados
        await asyncio.sleep(0.1)
        self._already_executed_this_tick = False
