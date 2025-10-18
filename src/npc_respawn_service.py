"""Servicio para manejar el respawn de NPCs."""

import asyncio
import logging
import random
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.npc import NPC
    from src.npc_service import NPCService

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
        respawn_delay = random.randint(npc.respawn_time, npc.respawn_time_max)  # noqa: S311

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

            # Spawnear el NPC en la misma posición
            new_npc = await self.npc_service.spawn_npc(
                npc_id=npc.npc_id,
                map_id=npc.map_id,
                x=npc.x,
                y=npc.y,
                heading=npc.heading,
            )

            if new_npc:
                logger.info(
                    "NPC %s respawneado en (%d,%d) mapa %d (CharIndex: %d)",
                    new_npc.name,
                    new_npc.x,
                    new_npc.y,
                    new_npc.map_id,
                    new_npc.char_index,
                )
            else:
                logger.warning(
                    "No se pudo respawnear NPC %s (npc_id=%d) en (%d,%d) mapa %d",
                    npc.name,
                    npc.npc_id,
                    npc.x,
                    npc.y,
                    npc.map_id,
                )

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
