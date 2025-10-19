"""Componente para enviar información de personajes al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import (
    build_character_change_response,
    build_character_create_response,
    build_character_move_response,
    build_character_remove_response,
)

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class CharacterMessageSender:
    """Maneja el envío de información de personajes al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de personajes.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_character_create(
        self,
        char_index: int,
        body: int,
        head: int,
        heading: int,
        x: int,
        y: int,
        weapon: int = 0,
        shield: int = 0,
        helmet: int = 0,
        fx: int = 0,
        loops: int = 0,
        name: str = "",
        nick_color: int = 0,
        privileges: int = 0,
    ) -> None:
        """Envía paquete CharacterCreate del protocolo AO estándar.

        Args:
            char_index: Índice del personaje (int16).
            body: ID del cuerpo (int16).
            head: ID de la cabeza (int16).
            heading: Dirección (byte): 1=Norte, 2=Este, 3=Sur, 4=Oeste.
            x: Posición X (byte).
            y: Posición Y (byte).
            weapon: ID del arma (int16), por defecto 0.
            shield: ID del escudo (int16), por defecto 0.
            helmet: ID del casco (int16), por defecto 0.
            fx: ID del efecto visual (int16), por defecto 0.
            loops: Número de loops del efecto (int16), por defecto 0.
            name: Nombre del personaje (string), por defecto vacío.
            nick_color: Color del nick (byte), por defecto 0.
            privileges: Privilegios del personaje (byte), por defecto 0.
        """
        response = build_character_create_response(
            char_index=char_index,
            body=body,
            head=head,
            heading=heading,
            x=x,
            y=y,
            weapon=weapon,
            shield=shield,
            helmet=helmet,
            fx=fx,
            loops=loops,
            name=name,
            nick_color=nick_color,
            privileges=privileges,
        )
        logger.debug(
            "[%s] Enviando CHARACTER_CREATE: charIndex=%d, name=%s, pos=(%d,%d)",
            self.connection.address,
            char_index,
            name,
            x,
            y,
        )
        await self.connection.send(response)

    async def send_character_change(
        self,
        char_index: int,
        body: int = 0,
        head: int = 0,
        heading: int = 0,
        weapon: int = 0,
        shield: int = 0,
        helmet: int = 0,
        fx: int = 0,
        loops: int = 0,
    ) -> None:
        """Envía paquete CharacterChange del protocolo AO estándar.

        Args:
            char_index: Índice del personaje (int16).
            body: ID del cuerpo (int16).
            head: ID de la cabeza (int16).
            heading: Dirección (byte).
            weapon: ID del arma (int16).
            shield: ID del escudo (int16).
            helmet: ID del casco (int16).
            fx: ID del efecto visual (int16).
            loops: Número de loops del efecto (int16).
        """
        response = build_character_change_response(
            char_index=char_index,
            body=body,
            head=head,
            heading=heading,
            weapon=weapon,
            shield=shield,
            helmet=helmet,
            fx=fx,
            loops=loops,
        )
        logger.debug(
            "[%s] Enviando CHARACTER_CHANGE: charIndex=%d heading=%s",
            self.connection.address,
            char_index,
            heading,
        )
        await self.connection.send(response)

    async def send_character_remove(self, char_index: int) -> None:
        """Envía paquete CharacterRemove del protocolo AO estándar.

        Args:
            char_index: Índice del personaje a remover (int16).
        """
        response = build_character_remove_response(char_index=char_index)
        logger.debug(
            "[%s] Enviando CHARACTER_REMOVE: charIndex=%d", self.connection.address, char_index
        )
        await self.connection.send(response)

    async def send_character_move(self, char_index: int, x: int, y: int) -> None:
        """Envía el packet CHARACTER_MOVE para notificar movimiento de un personaje.

        Args:
            char_index: Índice del personaje que se mueve.
            x: Nueva posición X.
            y: Nueva posición Y.
        """
        response = build_character_move_response(char_index, x, y)
        await self.connection.send(response)
