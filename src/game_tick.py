"""Sistema de tick periódico genérico para efectos del juego.

Sistema configurable que permite aplicar diferentes efectos periódicos
a los jugadores conectados (hambre, sed, reducción de oro, etc.).
"""

import asyncio
import contextlib
import logging
from typing import TYPE_CHECKING

from src.effect_gold_decay import GoldDecayEffect
from src.effect_hunger_thirst import HungerThirstEffect
from src.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class GameTick:
    """Sistema de tick genérico que aplica efectos periódicos a jugadores conectados."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        effects: list[TickEffect] | None = None,
        tick_interval: float = 1.0,
    ) -> None:
        """Inicializa el sistema de tick.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener jugadores conectados.
            effects: Lista de efectos a aplicar (por defecto vacía).
            tick_interval: Intervalo del tick en segundos (por defecto 1 segundo).
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.effects = effects or []
        self.tick_interval = tick_interval
        self._task: asyncio.Task[None] | None = None
        self._running = False

    def add_effect(self, effect: TickEffect) -> None:
        """Agrega un efecto al sistema de tick.

        Args:
            effect: Efecto a agregar.
        """
        self.effects.append(effect)
        logger.info("Efecto agregado: %s", effect.get_name())

    async def _tick_loop(self) -> None:
        """Loop principal del tick que procesa todos los jugadores conectados."""
        logger.info(
            "Sistema de tick iniciado (intervalo: %.1fs, efectos: %d)",
            self.tick_interval,
            len(self.effects),
        )

        while self._running:
            try:
                # Obtener todos los user_ids conectados
                connected_user_ids = self.map_manager.get_all_connected_user_ids()

                # Aplicar cada efecto a cada jugador
                for effect in self.effects:
                    for user_id in connected_user_ids:
                        try:
                            message_sender = self.map_manager.get_message_sender(user_id)
                            await effect.apply(user_id, self.player_repo, message_sender)
                        except Exception:
                            logger.exception(
                                "Error aplicando efecto %s a user_id %d",
                                effect.get_name(),
                                user_id,
                            )

                # Esperar hasta el próximo tick
                await asyncio.sleep(self.tick_interval)

            except asyncio.CancelledError:
                logger.info("Tick del juego cancelado")
                break
            except Exception:
                logger.exception("Error en el loop de tick del juego")
                await asyncio.sleep(self.tick_interval)

    def start(self) -> None:
        """Inicia el sistema de tick."""
        if self._running:
            logger.warning("El sistema de tick ya está ejecutándose")
            return

        self._running = True
        self._task = asyncio.create_task(self._tick_loop())
        logger.info("Sistema de tick iniciado con %d efectos", len(self.effects))

    async def stop(self) -> None:
        """Detiene el sistema de tick."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("Sistema de tick detenido")


# Re-exportar TickEffect para compatibilidad con imports existentes
__all__ = ["GameTick", "GoldDecayEffect", "HungerThirstEffect", "TickEffect"]
