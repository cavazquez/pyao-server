"""Componente para enviar mensajes de efectos de estado al cliente."""

import logging
from typing import TYPE_CHECKING

from src.network.msg_status_effects import (
    build_blind_no_more_response,
    build_blind_response,
    build_dumb_no_more_response,
    build_dumb_response,
    build_paralize_ok_response,
    build_rest_ok_response,
    build_set_invisible_response,
    build_update_tag_and_status_response,
)

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class StatusEffectsMessageSender:
    """Maneja el envío de mensajes de efectos de estado al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de efectos de estado.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_blind(self) -> None:
        """Envía paquete BLIND para activar efecto de ceguera."""
        response = build_blind_response()
        logger.info("[%s] Enviando BLIND", self.connection.address)
        await self.connection.send(response)

    async def send_blind_no_more(self) -> None:
        """Envía paquete BLIND_NO_MORE para desactivar efecto de ceguera."""
        response = build_blind_no_more_response()
        logger.info("[%s] Enviando BLIND_NO_MORE", self.connection.address)
        await self.connection.send(response)

    async def send_dumb(self) -> None:
        """Envía paquete DUMB para activar efecto de estupidez."""
        response = build_dumb_response()
        logger.info("[%s] Enviando DUMB", self.connection.address)
        await self.connection.send(response)

    async def send_dumb_no_more(self) -> None:
        """Envía paquete DUMB_NO_MORE para desactivar efecto de estupidez."""
        response = build_dumb_no_more_response()
        logger.info("[%s] Enviando DUMB_NO_MORE", self.connection.address)
        await self.connection.send(response)

    async def send_paralize_ok(self) -> None:
        """Envía paquete PARALIZE_OK para confirmar parálisis/inmovilización."""
        response = build_paralize_ok_response()
        logger.info("[%s] Enviando PARALIZE_OK", self.connection.address)
        await self.connection.send(response)

    async def send_rest_ok(self) -> None:
        """Envía paquete REST_OK para confirmar descanso."""
        response = build_rest_ok_response()
        logger.info("[%s] Enviando REST_OK", self.connection.address)
        await self.connection.send(response)

    async def send_set_invisible(self, char_index: int, invisible: bool) -> None:
        """Envía paquete SET_INVISIBLE para marcar personaje como invisible/visible.

        Args:
            char_index: Índice del personaje.
            invisible: True para hacer visible (el cliente invierte la lógica).
        """
        response = build_set_invisible_response(char_index, invisible)
        logger.info(
            "[%s] Enviando SET_INVISIBLE: charIndex=%d, invisible=%s",
            self.connection.address,
            char_index,
            invisible,
        )
        await self.connection.send(response)

    async def send_update_tag_and_status(
        self, char_index: int, nick_color: int, user_tag: str
    ) -> None:
        """Envía paquete UPDATE_TAG_AND_STATUS para actualizar nick color y tag.

        Args:
            char_index: Índice del personaje.
            nick_color: Color del nick (0=Ciudadano, 1=Criminal, 2=Newbie, etc.).
            user_tag: Nombre/tag del personaje.
        """
        response = build_update_tag_and_status_response(char_index, nick_color, user_tag)
        logger.info(
            "[%s] Enviando UPDATE_TAG_AND_STATUS: charIndex=%d, nickColor=%d, tag=%s",
            self.connection.address,
            char_index,
            nick_color,
            user_tag,
        )
        await self.connection.send(response)
