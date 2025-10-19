"""Componente para enviar efectos visuales al cliente."""

import logging
from typing import TYPE_CHECKING

from src.audio_constants import FXLoops, VisualEffectID
from src.msg import build_create_fx_response

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class VisualEffectsMessageSender:
    """Maneja el envío de efectos visuales al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de efectos visuales.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_create_fx(self, char_index: int, fx: int, loops: int) -> None:
        """Envía paquete CreateFX para mostrar un efecto visual en el cliente.

        Args:
            char_index: ID del personaje/objeto que genera el efecto.
            fx: ID del efecto visual.
            loops: Número de loops. -1 = infinito, 0 = una vez, >0 = número específico.
        """
        response = build_create_fx_response(char_index=char_index, fx=fx, loops=loops)
        logger.debug(
            "[%s] Enviando CREATE_FX: char_index=%d, fx=%d, loops=%d",
            self.connection.address,
            char_index,
            fx,
            loops,
        )
        await self.connection.send(response)

    async def send_create_fx_at_position(self, _x: int, _y: int, fx: int, loops: int) -> None:
        """Envía efecto visual en una posición específica del mapa.

        Args:
            _x: Coordenada X (no usado por ahora).
            _y: Coordenada Y (no usado por ahora).
            fx: ID del efecto visual.
            loops: Número de loops.
        """
        # Por ahora usamos char_index=0 para efectos en el terreno
        # TODO: Implementar CREATE_FX con coordenadas si el protocolo lo soporta
        await self.send_create_fx(char_index=0, fx=fx, loops=loops)

    # Métodos de conveniencia para efectos comunes
    async def play_effect_spawn(self, char_index: int) -> None:
        """Muestra efecto de spawn/aparición en un personaje."""
        await self.send_create_fx(
            char_index=char_index, fx=VisualEffectID.SPAWN_BLUE, loops=FXLoops.ONCE
        )

    async def play_effect_heal(self, char_index: int) -> None:
        """Muestra efecto de curación en un personaje."""
        await self.send_create_fx(char_index=char_index, fx=VisualEffectID.HEAL, loops=FXLoops.ONCE)

    async def play_effect_meditation(self, char_index: int) -> None:
        """Muestra efecto de meditación en un personaje."""
        await self.send_create_fx(
            char_index=char_index, fx=VisualEffectID.MEDITATION, loops=FXLoops.INFINITE
        )

    async def play_effect_explosion(self, char_index: int) -> None:
        """Muestra efecto de explosión."""
        await self.send_create_fx(
            char_index=char_index, fx=VisualEffectID.EXPLOSION, loops=FXLoops.ONCE
        )
