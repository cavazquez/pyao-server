"""Efecto periódico de envenenamiento para NPCs."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect
from src.services.npc.rewards.poison import poison_tick

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_death_service import NPCDeathService
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
        npc_death_service: NPCDeathService | None = None,
    ) -> None:
        """Inicializa el efecto de envenenamiento de NPCs.

        Args:
            npc_service: Servicio de NPCs.
            interval_seconds: Intervalo en segundos entre aplicaciones del efecto.
            npc_death_service: Liquidador común de recompensas, también para veneno.
        """
        self.npc_service = npc_service
        self.interval_seconds = interval_seconds
        self.npc_death_service = npc_death_service
        self._already_executed_this_tick = False

    async def apply(
        self,
        user_id: int,  # ruff: ignore[unused-method-argument]
        player_repo: PlayerRepository,  # ruff: ignore[unused-method-argument]
        message_sender: MessageSender | None,  # ruff: ignore[unused-method-argument]
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
        asyncio.create_task(self._reset_execution_flag())  # ruff: ignore[asyncio-dangling-task]

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
        result = await poison_tick(
            self.npc_service.npc_repository.redis.redis, npc, current_time, self.interval_seconds
        )
        npc.hp = int(result["new_hp"])
        if result["died"] and self.npc_death_service:
            await self.npc_death_service.handle_npc_death(
                npc, int(result["killer"]), npc.level * 10, None, death_reason="veneno"
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

    def get_name(self) -> str:
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "NPCPoison"
