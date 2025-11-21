"""Sistema de tick periódico genérico para efectos del juego.

Sistema configurable que permite aplicar diferentes efectos periódicos
a los jugadores conectados (hambre, sed, reducción de oro, etc.).
"""

import asyncio
import contextlib
import logging
import time
from typing import TYPE_CHECKING, Any, cast

from src.effects.effect_gold_decay import GoldDecayEffect
from src.effects.effect_hunger_thirst import HungerThirstEffect
from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
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
        # Métricas de rendimiento
        self._metrics: dict[str, Any] = {
            "total_ticks": 0,
            "total_time_ms": 0.0,
            "max_tick_time_ms": 0.0,
            "effect_metrics": {},  # {effect_name: {total_time_ms, count, max_time_ms}}
        }

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
                # Iniciar profiling del tick completo
                tick_start_time = time.perf_counter()

                # Obtener todos los user_ids conectados
                connected_user_ids = self.map_manager.get_all_connected_user_ids()

                if not connected_user_ids:
                    # No hay jugadores conectados, solo esperar
                    await asyncio.sleep(self.tick_interval)
                    continue

                # Crear todas las tareas para procesar en paralelo
                # Esto permite que todos los efectos de todos los jugadores
                # se procesen simultáneamente
                tasks = []
                for effect in self.effects:
                    for user_id in connected_user_ids:
                        message_sender = self.map_manager.get_message_sender(user_id)
                        # Crear tarea con manejo de excepciones incluido y profiling
                        task = self._apply_effect_safe_with_metrics(effect, user_id, message_sender)
                        tasks.append(task)

                # Ejecutar todas las tareas en paralelo
                # return_exceptions=True para que un error no detenga todo el tick
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)

                # Calcular tiempo del tick completo
                tick_elapsed_ms = (time.perf_counter() - tick_start_time) * 1000
                self._metrics["total_ticks"] = cast("int", self._metrics["total_ticks"]) + 1
                self._metrics["total_time_ms"] = (
                    cast("float", self._metrics["total_time_ms"]) + tick_elapsed_ms
                )
                self._metrics["max_tick_time_ms"] = max(
                    cast("float", self._metrics["max_tick_time_ms"]), tick_elapsed_ms
                )

                # Log de métricas cada 50 ticks
                if cast("int", self._metrics["total_ticks"]) % 50 == 0:
                    self._log_metrics()

                # Esperar hasta el próximo tick
                await asyncio.sleep(self.tick_interval)

            except asyncio.CancelledError:
                logger.info("Tick del juego cancelado")
                break
            except Exception:
                logger.exception("Error en el loop de tick del juego")
                await asyncio.sleep(self.tick_interval)

    async def _apply_effect_safe(
        self,
        effect: TickEffect,
        user_id: int,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica un efecto a un jugador con manejo de excepciones.

        Args:
            effect: Efecto a aplicar.
            user_id: ID del jugador.
            message_sender: MessageSender del jugador.
        """
        try:
            await effect.apply(user_id, self.player_repo, message_sender)
        except Exception:
            logger.exception(
                "Error aplicando efecto %s a user_id %d",
                effect.get_name(),
                user_id,
            )

    async def _apply_effect_safe_with_metrics(
        self,
        effect: TickEffect,
        user_id: int,
        message_sender: MessageSender | None,
    ) -> None:
        """Aplica un efecto a un jugador con métricas de rendimiento.

        Args:
            effect: Efecto a aplicar.
            user_id: ID del jugador.
            message_sender: MessageSender del jugador.
        """
        effect_name = effect.get_name()
        start_time = time.perf_counter()

        try:
            await effect.apply(user_id, self.player_repo, message_sender)
        except Exception:
            logger.exception(
                "Error aplicando efecto %s a user_id %d",
                effect_name,
                user_id,
            )
        finally:
            # Actualizar métricas del efecto
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            effect_metrics_dict = cast(
                "dict[str, dict[str, float | int]]", self._metrics["effect_metrics"]
            )
            if effect_name not in effect_metrics_dict:
                effect_metrics_dict[effect_name] = {
                    "total_time_ms": 0.0,
                    "count": 0,
                    "max_time_ms": 0.0,
                }
            effect_metrics = effect_metrics_dict[effect_name]
            effect_metrics["total_time_ms"] = (
                cast("float", effect_metrics["total_time_ms"]) + elapsed_ms
            )
            effect_metrics["count"] = cast("int", effect_metrics["count"]) + 1
            effect_metrics["max_time_ms"] = max(
                cast("float", effect_metrics["max_time_ms"]), elapsed_ms
            )

    def _log_metrics(self) -> None:
        """Registra las métricas de rendimiento."""
        total_ticks = cast("int", self._metrics["total_ticks"])
        total_time_ms = cast("float", self._metrics["total_time_ms"])
        max_tick_time_ms = cast("float", self._metrics["max_tick_time_ms"])

        avg_tick_time_ms = total_time_ms / total_ticks if total_ticks > 0 else 0.0

        logger.info(
            "GameTick metrics: %d ticks, avg=%.2fms, max=%.2fms",
            total_ticks,
            avg_tick_time_ms,
            max_tick_time_ms,
        )

        # Log de métricas por efecto
        effect_metrics_dict = cast(
            "dict[str, dict[str, float | int]]", self._metrics["effect_metrics"]
        )
        for effect_name, metrics in effect_metrics_dict.items():
            count = cast("int", metrics["count"])
            if count > 0:
                total_effect_time_ms = cast("float", metrics["total_time_ms"])
                avg_effect_time_ms = total_effect_time_ms / count
                max_effect_time_ms = cast("float", metrics["max_time_ms"])
                logger.info(
                    "  Effect '%s': %d calls, avg=%.2fms, max=%.2fms",
                    effect_name,
                    count,
                    avg_effect_time_ms,
                    max_effect_time_ms,
                )

    def get_metrics(self) -> dict[str, Any]:
        """Obtiene las métricas de rendimiento del GameTick.

        Returns:
            Diccionario con métricas de rendimiento.
        """
        total_ticks = cast("int", self._metrics["total_ticks"])
        total_time_ms = cast("float", self._metrics["total_time_ms"])
        max_tick_time_ms = cast("float", self._metrics["max_tick_time_ms"])

        avg_tick_time_ms = total_time_ms / total_ticks if total_ticks > 0 else 0.0

        effect_metrics_summary: dict[str, dict[str, float | int]] = {}
        effect_metrics_dict = cast(
            "dict[str, dict[str, float | int]]", self._metrics["effect_metrics"]
        )
        for effect_name, metrics in effect_metrics_dict.items():
            count = cast("int", metrics["count"])
            if count > 0:
                total_effect_time_ms = cast("float", metrics["total_time_ms"])
                avg_effect_time_ms = total_effect_time_ms / count
                max_effect_time_ms = cast("float", metrics["max_time_ms"])
                effect_metrics_summary[effect_name] = {
                    "count": count,
                    "avg_time_ms": avg_effect_time_ms,
                    "max_time_ms": max_effect_time_ms,
                }

        return {
            "total_ticks": total_ticks,
            "avg_tick_time_ms": avg_tick_time_ms,
            "max_tick_time_ms": max_tick_time_ms,
            "effects": effect_metrics_summary,
        }

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
