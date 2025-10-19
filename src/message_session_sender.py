"""Componente para enviar mensajes de sesión y login al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg_session import (
    build_attributes_response,
    build_dice_roll_response,
    build_logged_response,
    build_pong_response,
    build_user_char_index_in_server_response,
)

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class SessionMessageSender:
    """Maneja el envío de mensajes de sesión, login y creación de personaje al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de sesión.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_dice_roll(
        self, strength: int, agility: int, intelligence: int, charisma: int, constitution: int
    ) -> None:
        """Envía el resultado de una tirada de dados al cliente.

        Args:
            strength: Valor de fuerza (6-18).
            agility: Valor de agilidad (6-18).
            intelligence: Valor de inteligencia (6-18).
            charisma: Valor de carisma (6-18).
            constitution: Valor de constitución (6-18).
        """
        response = build_dice_roll_response(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )
        logger.info(
            "[%s] Enviando DICE_ROLL: STR=%d AGI=%d INT=%d CHA=%d CON=%d",
            self.connection.address,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )
        await self.connection.send(response)

    async def send_attributes(
        self, strength: int, agility: int, intelligence: int, charisma: int, constitution: int
    ) -> None:
        """Envía los atributos del personaje al cliente.

        Args:
            strength: Valor de fuerza.
            agility: Valor de agilidad.
            intelligence: Valor de inteligencia.
            charisma: Valor de carisma.
            constitution: Valor de constitución.
        """
        response = build_attributes_response(
            strength=strength,
            agility=agility,
            intelligence=intelligence,
            charisma=charisma,
            constitution=constitution,
        )
        logger.info(
            "[%s] Enviando ATTRIBUTES: STR=%d AGI=%d INT=%d CHA=%d CON=%d",
            self.connection.address,
            strength,
            agility,
            intelligence,
            charisma,
            constitution,
        )
        await self.connection.send(response)

    async def send_logged(self, user_class: int) -> None:
        """Envía paquete Logged para confirmar login exitoso.

        Args:
            user_class: Clase del personaje (1 byte).
        """
        response = build_logged_response(user_class=user_class)
        logger.info("[%s] Enviando LOGGED: userClass=%d", self.connection.address, user_class)
        await self.connection.send(response)

    async def send_user_char_index_in_server(self, char_index: int) -> None:
        """Envía el índice del personaje del jugador en el servidor.

        Args:
            char_index: Índice del personaje del jugador en el servidor (int16).
        """
        response = build_user_char_index_in_server_response(char_index=char_index)
        logger.info(
            "[%s] Enviando USER_CHAR_INDEX_IN_SERVER: charIndex=%d",
            self.connection.address,
            char_index,
        )
        await self.connection.send(response)

    async def send_pong(self) -> None:
        """Envía paquete PONG en respuesta a un PING del cliente."""
        response = build_pong_response()
        logger.debug("[%s] Enviando PONG", self.connection.address)
        await self.connection.send(response)
