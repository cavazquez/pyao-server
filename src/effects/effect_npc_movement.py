"""Efecto de movimiento aleatorio de NPCs."""

import asyncio
import logging
import random
import time
from typing import TYPE_CHECKING

from src.constants.gameplay import DEFAULT_MAX_NPCS_PER_TICK, DEFAULT_NPC_CHUNK_SIZE
from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)

# Alias for backwards compatibility
DEFAULT_CHUNK_SIZE = DEFAULT_NPC_CHUNK_SIZE


class NPCMovementEffect(TickEffect):
    """Efecto que hace que los NPCs se muevan aleatoriamente."""

    def __init__(
        self,
        npc_service: NPCService,
        interval_seconds: float = 5.0,
        max_npcs_per_tick: int = DEFAULT_MAX_NPCS_PER_TICK,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
    ) -> None:
        """Inicializa el efecto de movimiento de NPCs.

        Args:
            npc_service: Servicio de NPCs.
            interval_seconds: Intervalo entre movimientos en segundos.
            max_npcs_per_tick: Máximo de NPCs procesados por tick (optimización).
            chunk_size: Tamaño de chunk para procesamiento paralelo.
        """
        self.npc_service = npc_service
        self.interval_seconds = interval_seconds
        self.max_npcs_per_tick = max_npcs_per_tick
        self.chunk_size = chunk_size
        self._already_executed_this_tick = False
        self._player_repo: PlayerRepository | None = None
        # Métricas
        self._metrics = {
            "total_npcs_processed": 0,
            "total_ticks": 0,
            "total_time_ms": 0.0,
            "max_time_ms": 0.0,
        }

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:
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

        # Iniciar profiling
        start_time = time.perf_counter()

        # Obtener todos los NPCs del mundo
        all_npcs = self.npc_service.map_manager.get_all_npcs()

        if not all_npcs:
            logger.debug("No hay NPCs en el mundo para mover")
            return

        # Filtrar solo NPCs hostiles
        hostile_npcs = [npc for npc in all_npcs if npc.is_hostile]

        if not hostile_npcs:
            logger.debug("No hay NPCs hostiles para mover")
            return

        # OPTIMIZACIÓN: Limitar NPCs procesados por tick (chunks)
        # Seleccionar máximo max_npcs_per_tick NPCs aleatoriamente
        npcs_to_move = random.sample(hostile_npcs, min(len(hostile_npcs), self.max_npcs_per_tick))

        logger.debug(
            "Moviendo NPCs: %d/%d hostiles seleccionados (máx: %d por tick)",
            len(npcs_to_move),
            len(hostile_npcs),
            self.max_npcs_per_tick,
        )

        # OPTIMIZACIÓN: Procesamiento paralelo por chunks
        # Dividir NPCs en chunks y procesar cada chunk en paralelo
        chunks = [
            npcs_to_move[i : i + self.chunk_size]
            for i in range(0, len(npcs_to_move), self.chunk_size)
        ]

        # Crear tareas para procesar cada chunk en paralelo
        tasks = []
        for chunk in chunks:
            # Procesar chunk en paralelo
            chunk_tasks = [self._move_npc_with_ai(npc, self._player_repo) for npc in chunk]
            tasks.extend(chunk_tasks)

        # Ejecutar todas las tareas en paralelo
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # Calcular métricas
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        self._metrics["total_npcs_processed"] += len(npcs_to_move)
        self._metrics["total_ticks"] += 1
        self._metrics["total_time_ms"] += elapsed_ms
        self._metrics["max_time_ms"] = max(self._metrics["max_time_ms"], elapsed_ms)

        # Log de métricas cada 10 ticks
        if self._metrics["total_ticks"] % 10 == 0:
            avg_time_ms = (
                self._metrics["total_time_ms"] / self._metrics["total_ticks"]
                if self._metrics["total_ticks"] > 0
                else 0
            )
            logger.info(
                "NPCMovement metrics: %d NPCs procesados en %d ticks, avg=%.2fms, max=%.2fms",
                self._metrics["total_npcs_processed"],
                self._metrics["total_ticks"],
                avg_time_ms,
                self._metrics["max_time_ms"],
            )

    async def _move_npc_with_ai(self, npc: NPC, player_repo: PlayerRepository | None) -> None:
        """Mueve un NPC con IA: persigue jugadores cercanos o se mueve aleatoriamente.

        Args:
            npc: Instancia del NPC a mover.
            player_repo: Repositorio de jugadores para obtener posiciones.
        """
        # Verificar si el NPC está paralizado
        current_time = time.time()
        if npc.paralyzed_until > 0.0 and current_time < npc.paralyzed_until:
            logger.debug(
                "NPC %s no puede moverse (IA): está paralizado (queda %.1fs)",
                npc.name,
                npc.paralyzed_until - current_time,
            )
            return

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
        # Verificar si el NPC está paralizado
        current_time = time.time()
        if npc.paralyzed_until > 0.0 and current_time < npc.paralyzed_until:
            logger.debug(
                "NPC %s no puede moverse: está paralizado (queda %.1fs)",
                npc.name,
                npc.paralyzed_until - current_time,
            )
            return

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
        # Verificar si el NPC está paralizado
        current_time = time.time()
        if npc.paralyzed_until > 0.0 and current_time < npc.paralyzed_until:
            logger.debug(
                "NPC %s no puede moverse aleatoriamente: está paralizado (queda %.1fs)",
                npc.name,
                npc.paralyzed_until - current_time,
            )
            return

        # Elegir dirección aleatoria (1=Norte, 2=Este, 3=Sur, 4=Oeste)
        direction = random.randint(1, 4)

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

    def get_metrics(self) -> dict[str, float | int]:
        """Obtiene las métricas de rendimiento del efecto.

        Returns:
            Diccionario con métricas de rendimiento.
        """
        avg_time_ms = (
            self._metrics["total_time_ms"] / self._metrics["total_ticks"]
            if self._metrics["total_ticks"] > 0
            else 0.0
        )
        return {
            "total_npcs_processed": self._metrics["total_npcs_processed"],
            "total_ticks": self._metrics["total_ticks"],
            "avg_time_ms": avg_time_ms,
            "max_time_ms": self._metrics["max_time_ms"],
            "avg_npcs_per_tick": (
                self._metrics["total_npcs_processed"] / self._metrics["total_ticks"]
                if self._metrics["total_ticks"] > 0
                else 0.0
            ),
        }
