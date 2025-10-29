"""Servicio para manejar el respawn de NPCs."""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.npc import NPC
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)


class NPCRespawnService:
    """Servicio que maneja el respawn de NPCs después de morir."""

    def __init__(self, npc_service: NPCService) -> None:
        """Inicializa el servicio de respawn.

        Args:
            npc_service: Servicio de NPCs para spawnear nuevas instancias.
        """
        self.npc_service = npc_service
        self._respawn_tasks: dict[str, asyncio.Task[None]] = {}  # instance_id -> Task

    def _find_random_free_position(
        self, map_id: int, center_x: int, center_y: int, radius: int = 5
    ) -> tuple[int, int] | None:
        """Busca una posición libre aleatoria cerca de un punto central.

        Args:
            map_id: ID del mapa.
            center_x: Coordenada X central.
            center_y: Coordenada Y central.
            radius: Radio de búsqueda alrededor del centro.

        Returns:
            Tupla (x, y) con una posición libre, o None si no encuentra.
        """
        # Generar posición aleatoria dentro del radio
        offset_x = random.randint(-radius, radius)
        offset_y = random.randint(-radius, radius)

        x = center_x + offset_x
        y = center_y + offset_y

        # Verificar límites del mapa (1-100)
        if x < 1 or x > 100 or y < 1 or y > 100:  # noqa: PLR2004
            return None

        # Verificar si la posición está libre
        if self.npc_service.map_manager.can_move_to(map_id, x, y):
            return (x, y)

        # Posición bloqueada
        occupant = self.npc_service.map_manager.get_tile_occupant(map_id, x, y)
        if occupant:
            logger.info("Posición (%d,%d) mapa %d bloqueada por: %s", x, y, map_id, occupant)
        else:
            logger.info("Posición (%d,%d) mapa %d bloqueada (tile del mapa)", x, y, map_id)

        return None

    async def schedule_respawn(self, npc: NPC) -> None:
        """Programa el respawn de un NPC después de que muere.

        Args:
            npc: NPC que murió y debe respawnear.
        """
        if npc.respawn_time <= 0:
            logger.debug(
                "NPC %s no tiene respawn configurado (respawn_time=%d)", npc.name, npc.respawn_time
            )
            return

        # Calcular tiempo aleatorio de respawn entre min y max
        respawn_delay = random.randint(npc.respawn_time, npc.respawn_time_max)

        # Cancelar respawn anterior si existe
        if npc.instance_id in self._respawn_tasks:
            self._respawn_tasks[npc.instance_id].cancel()

        # Crear tarea de respawn
        task = asyncio.create_task(self._respawn_after_delay(npc, respawn_delay))
        self._respawn_tasks[npc.instance_id] = task

        logger.info(
            "Respawn programado para NPC %s en %d segundos (rango: %d-%d) (pos: %d,%d mapa: %d)",
            npc.name,
            respawn_delay,
            npc.respawn_time,
            npc.respawn_time_max,
            npc.x,
            npc.y,
            npc.map_id,
        )

    async def _respawn_after_delay(self, npc: NPC, delay_seconds: int) -> None:
        """Espera el tiempo de respawn y luego spawnea el NPC.

        Args:
            npc: NPC a respawnear.
            delay_seconds: Tiempo en segundos a esperar antes de respawnear.
        """
        try:
            # Esperar el tiempo de respawn
            await asyncio.sleep(delay_seconds)

            # Intentar respawnear hasta encontrar una posición libre
            attempt = 0
            while True:
                attempt += 1

                # Buscar posición libre aleatoria cercana a la posición original
                spawn_pos = self._find_random_free_position(npc.map_id, npc.x, npc.y, radius=5)

                if spawn_pos:
                    spawn_x, spawn_y = spawn_pos

                    # Intentar spawnear el NPC
                    try:
                        new_npc = await self.npc_service.spawn_npc(
                            npc_id=npc.npc_id,
                            map_id=npc.map_id,
                            x=spawn_x,
                            y=spawn_y,
                            heading=npc.heading,
                        )

                        if new_npc:
                            logger.info(
                                "NPC %s respawneado en (%d,%d) mapa %d (CharIndex: %d) "
                                "[original: (%d,%d), intento: %d]",
                                new_npc.name,
                                new_npc.x,
                                new_npc.y,
                                new_npc.map_id,
                                new_npc.char_index,
                                npc.x,
                                npc.y,
                                attempt,
                            )
                            break  # Respawn exitoso, salir del loop
                    except ValueError as e:
                        # Tile ocupado, intentar de nuevo
                        logger.info(
                            "Tile (%d,%d) bloqueado al intentar respawnear %s: %s",
                            spawn_x,
                            spawn_y,
                            npc.name,
                            e,
                        )

                # Si no encontró posición o falló el spawn, esperar un poco antes de reintentar
                if attempt % 10 == 0:
                    logger.warning(
                        "NPC %s: %d intentos de respawn sin éxito cerca de (%d,%d) mapa %d",
                        npc.name,
                        attempt,
                        npc.x,
                        npc.y,
                        npc.map_id,
                    )

                # Esperar 1 segundo antes de reintentar (no bloqueante)
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.debug("Respawn cancelado para NPC %s", npc.name)
        except Exception:
            logger.exception("Error al respawnear NPC %s", npc.name)
        finally:
            # Limpiar tarea completada
            if npc.instance_id in self._respawn_tasks:
                del self._respawn_tasks[npc.instance_id]

    def cancel_respawn(self, instance_id: str) -> None:
        """Cancela el respawn programado de un NPC.

        Args:
            instance_id: ID de instancia del NPC.
        """
        if instance_id in self._respawn_tasks:
            self._respawn_tasks[instance_id].cancel()
            del self._respawn_tasks[instance_id]
            logger.debug("Respawn cancelado para instance_id %s", instance_id)

    def cancel_all_respawns(self) -> None:
        """Cancela todos los respawns programados."""
        for task in self._respawn_tasks.values():
            task.cancel()
        self._respawn_tasks.clear()
        logger.info("Todos los respawns cancelados")

    def get_pending_respawns_count(self) -> int:
        """Retorna el número de respawns pendientes.

        Returns:
            Número de NPCs esperando respawn.
        """
        return len(self._respawn_tasks)
