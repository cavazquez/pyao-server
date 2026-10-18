"""Handler especializado para comandos de métricas."""

import asyncio
import logging
from itertools import islice
from typing import TYPE_CHECKING, Any

from src.network.session_manager import SessionManager

if TYPE_CHECKING:
    from src.game.game_tick import GameTick
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository

logger = logging.getLogger(__name__)
METRICS_BUDGET_SECONDS = 1.0
MAX_METRIC_EFFECTS = 32


class TalkMetricsHandler:
    """Handler especializado para comandos de métricas."""

    def __init__(
        self,
        game_tick: GameTick | None,
        message_sender: MessageSender,
        account_repo: AccountRepository | None = None,
        session_data: dict[str, Any] | None = None,
    ) -> None:
        """Inicializa el handler de métricas.

        Args:
            account_repo: Permisos persistidos de la cuenta autenticada.
            session_data: Sesión mutable que debe seguir perteneciendo al solicitante.
            game_tick: Sistema de GameTick para comandos de métricas.
            message_sender: Enviador de mensajes.
        """
        self.account_repo = account_repo
        self.session_data = session_data if session_data is not None else {}
        self.game_tick = game_tick
        self.message_sender = message_sender

    async def _send_metrics(self, user_id: int) -> None:
        """Maneja el comando /METRICS para mostrar métricas de rendimiento.

        Args:
            user_id: ID del usuario que solicita las métricas.
        """
        if not self.game_tick:
            await self.message_sender.send_console_msg(
                "Métricas no disponibles (GameTick no inicializado)",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return

        # Obtener métricas generales
        metrics = self.game_tick.get_metrics()

        # Construir mensaje de métricas
        lines = [
            "=== MÉTRICAS DE RENDIMIENTO ===",
            f"Total ticks: {metrics['total_ticks']}",
            f"Tiempo promedio: {metrics['avg_tick_time_ms']:.2f}ms",
            f"Tiempo máximo: {metrics['max_tick_time_ms']:.2f}ms",
        ]

        # Métricas por efecto
        if metrics.get("effects"):
            lines.append("\n--- Por Efecto ---")
            for effect_name, effect_metrics in islice(
                metrics["effects"].items(), MAX_METRIC_EFFECTS
            ):
                lines.append(
                    f"{effect_name}: {effect_metrics['count']} calls, "
                    f"avg={effect_metrics['avg_time_ms']:.2f}ms, "
                    f"max={effect_metrics['max_time_ms']:.2f}ms"
                )

        # Métricas específicas de NPCMovementEffect
        for effect in islice(self.game_tick.effects, MAX_METRIC_EFFECTS):
            if effect.get_name() == "NPCMovement" and hasattr(effect, "get_metrics"):
                npc_metrics = effect.get_metrics()
                lines.extend(
                    (
                        "\n--- NPC Movement ---",
                        f"NPCs procesados: {npc_metrics['total_npcs_processed']}",
                        f"Ticks: {npc_metrics['total_ticks']}",
                        f"Avg tiempo: {npc_metrics['avg_time_ms']:.2f}ms",
                        f"Max tiempo: {npc_metrics['max_time_ms']:.2f}ms",
                        f"NPCs/tick: {npc_metrics['avg_npcs_per_tick']:.2f}",
                    )
                )
                break

        # Enviar métricas línea por línea
        message = "\n".join(lines)
        if not await self._authorized(user_id):
            await self.message_sender.send_console_msg("Diagnóstico reservado a administración.")
            return
        await self.message_sender.send_multiline_console_msg(message[:8192])

        logger.info("Métricas solicitadas por user_id %d", user_id)

    async def _authorized(self, user_id: int) -> bool:
        if (
            not self.account_repo
            or SessionManager.get_user_id(self.session_data) != user_id
            or self.message_sender.connection.is_authenticated is not True
        ):
            return False
        allowed = await self.account_repo.is_gm_by_user_id(user_id)
        return (
            allowed is True
            and SessionManager.get_user_id(self.session_data) == user_id
            and self.message_sender.connection.is_authenticated is True
        )

    async def handle_metrics_command(self, user_id: int) -> None:
        """Autoriza antes de recopilar y antes de emitir, con presupuesto total de un segundo."""
        try:
            async with asyncio.timeout(METRICS_BUDGET_SECONDS):
                if not await self._authorized(user_id):
                    await self.message_sender.send_console_msg(
                        "Diagnóstico reservado a administración."
                    )
                    return
                await self._send_metrics(user_id)
        except TimeoutError:
            logger.warning("Presupuesto de METRICS agotado para user_id %d", user_id)
