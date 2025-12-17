"""Handler especializado para comandos de métricas."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.game_tick import GameTick
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TalkMetricsHandler:
    """Handler especializado para comandos de métricas."""

    def __init__(
        self,
        game_tick: GameTick | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de métricas.

        Args:
            game_tick: Sistema de GameTick para comandos de métricas.
            message_sender: Enviador de mensajes.
        """
        self.game_tick = game_tick
        self.message_sender = message_sender

    async def handle_metrics_command(self, user_id: int) -> None:
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
            for effect_name, effect_metrics in metrics["effects"].items():
                lines.append(
                    f"{effect_name}: {effect_metrics['count']} calls, "
                    f"avg={effect_metrics['avg_time_ms']:.2f}ms, "
                    f"max={effect_metrics['max_time_ms']:.2f}ms"
                )

        # Métricas específicas de NPCMovementEffect
        for effect in self.game_tick.effects:
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
        await self.message_sender.send_multiline_console_msg(message)

        logger.info("Métricas solicitadas por user_id %d", user_id)
