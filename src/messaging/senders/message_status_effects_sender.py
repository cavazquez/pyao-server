"""Componente para enviar mensajes de efectos de estado al cliente."""

import asyncio
import logging
import time
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
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class StatusEffectsMessageSender:
    """Maneja el envío de mensajes de efectos de estado al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de efectos de estado.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection
        self._status_lock = asyncio.Lock()
        self._paralyzed = False
        self._blind = False
        self._dumb = False

    async def send_blind(self) -> None:
        """Envía paquete BLIND para activar efecto de ceguera."""
        response = build_blind_response()
        logger.info("[%s] Enviando BLIND", self.connection.address)
        await self.connection.send(response)
        self._blind = True

    async def send_blind_no_more(self) -> None:
        """Envía paquete BLIND_NO_MORE para desactivar efecto de ceguera."""
        response = build_blind_no_more_response()
        logger.info("[%s] Enviando BLIND_NO_MORE", self.connection.address)
        await self.connection.send(response)
        self._blind = False

    async def send_dumb(self) -> None:
        """Envía paquete DUMB para activar efecto de estupidez."""
        response = build_dumb_response()
        logger.info("[%s] Enviando DUMB", self.connection.address)
        await self.connection.send(response)
        self._dumb = True

    async def send_dumb_no_more(self) -> None:
        """Envía paquete DUMB_NO_MORE para desactivar efecto de estupidez."""
        response = build_dumb_no_more_response()
        logger.info("[%s] Enviando DUMB_NO_MORE", self.connection.address)
        await self.connection.send(response)
        self._dumb = False

    async def send_paralize_ok(self) -> None:
        """Envía paquete PARALIZE_OK para confirmar parálisis/inmovilización."""
        async with self._status_lock:
            response = build_paralize_ok_response()
            await self.connection.send(response)
            self._paralyzed = not self._paralyzed

    async def sync_status(self, user_id: int, repository: PlayerRepository) -> None:
        """Lee dentro del lock y emite sólo transiciones, incluso con publicaciones concurrentes."""
        async with self._status_lock:
            stats = await repository.redis.hgetall(RedisKeys.player_user_stats(user_id))
            alive = int(stats.get("min_hp", stats.get("hp", 0))) > 0
            now = time.time()
            paralyzed = alive and float(stats.get("immobilized_until", 0)) > now
            blind = alive and float(stats.get("blinded_until", 0)) > now
            dumb = alive and float(stats.get("dumb_until", 0)) > now
            if paralyzed != self._paralyzed:
                await self.connection.send(build_paralize_ok_response())
                self._paralyzed = paralyzed
            if blind != self._blind:
                await self.connection.send(
                    build_blind_response() if blind else build_blind_no_more_response()
                )
                self._blind = blind
            if dumb != self._dumb:
                await self.connection.send(
                    build_dumb_response() if dumb else build_dumb_no_more_response()
                )
                self._dumb = dumb

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
