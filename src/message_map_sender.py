"""Componente para enviar información de mapa y posición al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import (
    build_block_position_response,
    build_change_map_response,
    build_object_create_response,
    build_object_delete_response,
    build_pos_update_response,
)

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class MapMessageSender:
    """Maneja el envío de información de mapa y posición al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de mapa.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_change_map(self, map_number: int, version: int = 0) -> None:
        """Envía paquete ChangeMap del protocolo AO estándar.

        Args:
            map_number: Número del mapa (int16).
            version: Versión del mapa (int16), por defecto 0.
        """
        response = build_change_map_response(map_number=map_number, version=version)
        logger.info(
            "[%s] Enviando CHANGE_MAP: map=%d, version=%d",
            self.connection.address,
            map_number,
            version,
        )
        await self.connection.send(response)

    async def send_pos_update(self, x: int, y: int) -> None:
        """Envía paquete PosUpdate del protocolo AO estándar.

        Args:
            x: Posición X del personaje (0-255).
            y: Posición Y del personaje (0-255).
        """
        response = build_pos_update_response(x=x, y=y)
        logger.info("[%s] Enviando POS_UPDATE: x=%d, y=%d", self.connection.address, x, y)
        await self.connection.send(response)

    async def send_object_create(self, x: int, y: int, grh_index: int) -> None:
        """Envía el packet OBJECT_CREATE para mostrar un item en el suelo.

        Args:
            x: Posición X del objeto.
            y: Posición Y del objeto.
            grh_index: Índice gráfico del objeto.
        """
        response = build_object_create_response(x, y, grh_index)
        logger.debug(
            "[%s] Enviando OBJECT_CREATE: pos=(%d,%d) grh=%d",
            self.connection.address,
            x,
            y,
            grh_index,
        )
        await self.connection.send(response)

    async def send_object_delete(self, x: int, y: int) -> None:
        """Envía el packet OBJECT_DELETE para remover un item del suelo.

        Args:
            x: Posición X del objeto.
            y: Posición Y del objeto.
        """
        response = build_object_delete_response(x, y)
        logger.debug("[%s] Enviando OBJECT_DELETE: pos=(%d,%d)", self.connection.address, x, y)
        await self.connection.send(response)

    async def send_block_position(self, x: int, y: int, blocked: bool) -> None:
        """Envía el packet BLOCK_POSITION para marcar un tile como bloqueado o no.

        Args:
            x: Posición X del tile.
            y: Posición Y del tile.
            blocked: True si está bloqueado, False si no.
        """
        response = build_block_position_response(x, y, blocked)
        logger.debug(
            "[%s] Enviando BLOCK_POSITION: pos=(%d,%d) blocked=%s",
            self.connection.address,
            x,
            y,
            blocked,
        )
        await self.connection.send(response)
