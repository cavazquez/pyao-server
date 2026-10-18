"""Doble clic de mapa: ID + x + y; el uso de slots corresponde a USE_ITEM."""

from src.tasks.interaction.task_left_click import TaskLeftClick

DOUBLE_CLICK_PACKET_BYTES = 3


class TaskDoubleClick(TaskLeftClick):
    """Resuelve coordenadas con el flujo de interacción de NPCs, puertas y carteles.

    Hereda la inyección de left_click_handler y player_repo. Ningún byte se
    interpreta como slot o CharIndex y la sesión determina el mapa efectivo.
    """

    async def execute(self) -> None:
        """Valida el layout exacto antes de ejecutar la interacción de mapa."""
        if len(self.data) != DOUBLE_CLICK_PACKET_BYTES:
            await self.message_sender.send_console_msg("Doble clic de mapa inválido")
            return
        await super().execute()
