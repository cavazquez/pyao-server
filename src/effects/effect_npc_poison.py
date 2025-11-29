"""Efecto periódico de envenenamiento para NPCs."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)

# Constantes de envenenamiento para NPCs
NPC_POISON_DAMAGE_PER_TICK = 5  # Daño por tick
NPC_POISON_TICK_INTERVAL = 2.0  # Segundos entre ticks de daño


class NPCPoisonEffect(TickEffect):
    """Efecto que aplica daño periódico a NPCs envenenados."""

    def __init__(
        self,
        npc_service: NPCService,
        interval_seconds: float = NPC_POISON_TICK_INTERVAL,
    ) -> None:
        """Inicializa el efecto de envenenamiento de NPCs.

        Args:
            npc_service: Servicio de NPCs.
            interval_seconds: Intervalo en segundos entre aplicaciones del efecto.
        """
        self.npc_service = npc_service
        self.interval_seconds = interval_seconds
        self._already_executed_this_tick = False

    async def apply(
        self,
        user_id: int,  # noqa: ARG002
        player_repo: PlayerRepository,  # noqa: ARG002
        message_sender: MessageSender | None,  # noqa: ARG002
    ) -> None:
        """Aplica el daño de envenenamiento a NPCs envenenados.

        Nota: Este efecto opera sobre NPCs globalmente, no por jugador.
        Solo se ejecuta una vez por tick.

        Args:
            user_id: ID del usuario (ignorado).
            player_repo: Repositorio de jugadores (ignorado).
            message_sender: MessageSender (ignorado).
        """
        # Solo ejecutar una vez por tick, no por cada jugador
        if self._already_executed_this_tick:
            return

        self._already_executed_this_tick = True

        # Resetear el flag después de un breve delay para el próximo tick
        asyncio.create_task(self._reset_execution_flag())  # noqa: RUF006

        current_time = time.time()

        # Obtener todos los NPCs del mundo
        all_npcs = self.npc_service.map_manager.get_all_npcs()

        if not all_npcs:
            return

        # Filtrar solo NPCs envenenados vivos
        poisoned_npcs = [npc for npc in all_npcs if npc.poisoned_until > 0.0 and npc.hp > 0]

        if not poisoned_npcs:
            return

        # Procesar NPCs envenenados en paralelo
        tasks = [self._process_poisoned_npc(npc, current_time) for npc in poisoned_npcs]

        # gather con return_exceptions=True para que un error en un NPC no afecte a los demás
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Contar errores si los hay
        errors = sum(1 for r in results if isinstance(r, Exception))
        if errors > 0:
            logger.warning(
                "Errores procesando envenenamiento de %d/%d NPCs", errors, len(poisoned_npcs)
            )

        logger.debug(
            "Procesado envenenamiento de %d NPCs en paralelo",
            len(poisoned_npcs),
        )

    async def _process_poisoned_npc(self, npc: NPC, current_time: float) -> None:
        """Procesa el daño de envenenamiento para un NPC.

        Args:
            npc: NPC envenenado.
            current_time: Timestamp actual.
        """
        # Verificar si el envenenamiento expiró
        if current_time >= npc.poisoned_until:
            # Limpiar el estado
            await self.npc_service.npc_repository.update_npc_poisoned_until(
                npc.instance_id, 0.0, poisoned_by_user_id=0
            )
            npc.poisoned_until = 0.0
            npc.poisoned_by_user_id = 0
            logger.debug("Envenenamiento expirado para NPC %s", npc.name)
            return

        # Verificar que el NPC esté vivo
        if npc.hp <= 0:
            # Limpiar envenenamiento si el NPC murió
            await self.npc_service.npc_repository.update_npc_poisoned_until(
                npc.instance_id, 0.0, poisoned_by_user_id=0
            )
            npc.poisoned_until = 0.0
            npc.poisoned_by_user_id = 0
            return

        # Aplicar daño de envenenamiento
        new_hp = max(0, npc.hp - NPC_POISON_DAMAGE_PER_TICK)

        # Actualizar HP en Redis
        await self.npc_service.npc_repository.update_npc_hp(npc.instance_id, new_hp)
        npc.hp = new_hp

        # Verificar si el NPC murió
        if new_hp <= 0:
            logger.info(
                "NPC %s murió por envenenamiento (HP: %d/%d, envenenado por user_id %d)",
                npc.name,
                new_hp,
                npc.max_hp,
                npc.poisoned_by_user_id,
            )
            # Limpiar envenenamiento al morir
            await self.npc_service.npc_repository.update_npc_poisoned_until(
                npc.instance_id, 0.0, poisoned_by_user_id=0
            )
            npc.poisoned_until = 0.0
            npc.poisoned_by_user_id = 0

            # Remover el NPC del juego usando el servicio de NPCs
            # Esto hará el broadcast CHARACTER_REMOVE a todos los jugadores
            await self.npc_service.remove_npc(npc)
        else:
            logger.debug(
                "NPC %s recibió daño de envenenamiento: %d -> %d HP (expira en %.1fs)",
                npc.name,
                npc.hp + NPC_POISON_DAMAGE_PER_TICK,
                new_hp,
                npc.poisoned_until - current_time,
            )

    async def _reset_execution_flag(self) -> None:
        """Resetea el flag de ejecución después de un breve delay."""
        await asyncio.sleep(0.1)
        self._already_executed_this_tick = False

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "NPCPoison"
