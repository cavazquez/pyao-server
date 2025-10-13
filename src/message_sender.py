"""Envío de mensajes específicos al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import (
    build_attributes_response,
    build_dice_roll_response,
    build_error_msg_response,
    build_logged_response,
    build_pos_update_response,
    build_update_hp_response,
    build_update_mana_response,
    build_update_sta_response,
    build_update_user_stats_response,
)

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class MessageSender:
    """Encapsula la lógica de envío de mensajes específicos del juego."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el enviador de mensajes.

        Args:
            connection: Conexión del cliente para enviar mensajes.
        """
        self.connection = connection

    async def send_dice_roll(
        self,
        strength: int,
        agility: int,
        intelligence: int,
        charisma: int,
        constitution: int,
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
        await self.connection.send(response)

    async def send_attributes(
        self,
        strength: int,
        agility: int,
        intelligence: int,
        charisma: int,
        constitution: int,
    ) -> None:
        """Envía los atributos del personaje al cliente usando PacketID 50.

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
        await self.connection.send(response)

    async def send_logged(self, user_class: int) -> None:
        """Envía paquete Logged del protocolo AO estándar.

        Args:
            user_class: Clase del personaje (1 byte).
        """
        response = build_logged_response(user_class=user_class)
        await self.connection.send(response)

    async def send_pos_update(self, x: int, y: int) -> None:
        """Envía paquete PosUpdate del protocolo AO estándar.

        Args:
            x: Posición X del personaje (0-255).
            y: Posición Y del personaje (0-255).
        """
        response = build_pos_update_response(x=x, y=y)
        await self.connection.send(response)

    async def send_error_msg(self, error_message: str) -> None:
        """Envía paquete ErrorMsg del protocolo AO estándar.

        Args:
            error_message: Mensaje de error.
        """
        response = build_error_msg_response(error_message=error_message)
        await self.connection.send(response)

    async def send_update_hp(self, hp: int) -> None:
        """Envía paquete UpdateHP del protocolo AO estándar.

        Args:
            hp: Puntos de vida actuales (int16).
        """
        response = build_update_hp_response(hp=hp)
        await self.connection.send(response)

    async def send_update_mana(self, mana: int) -> None:
        """Envía paquete UpdateMana del protocolo AO estándar.

        Args:
            mana: Puntos de mana actuales (int16).
        """
        response = build_update_mana_response(mana=mana)
        await self.connection.send(response)

    async def send_update_sta(self, stamina: int) -> None:
        """Envía paquete UpdateSta del protocolo AO estándar.

        Args:
            stamina: Puntos de stamina actuales (int16).
        """
        response = build_update_sta_response(stamina=stamina)
        await self.connection.send(response)

    async def send_update_user_stats(  # noqa: PLR0913, PLR0917
        self,
        max_hp: int,
        min_hp: int,
        max_mana: int,
        min_mana: int,
        max_sta: int,
        min_sta: int,
        gold: int,
        level: int,
        elu: int,
        experience: int,
    ) -> None:
        """Envía paquete UpdateUserStats del protocolo AO estándar.

        Args:
            max_hp: HP máximo (int16).
            min_hp: HP actual (int16).
            max_mana: Mana máximo (int16).
            min_mana: Mana actual (int16).
            max_sta: Stamina máxima (int16).
            min_sta: Stamina actual (int16).
            gold: Oro del jugador (int32).
            level: Nivel del jugador (byte).
            elu: Experiencia para subir de nivel (int32).
            experience: Experiencia total (int32).
        """
        response = build_update_user_stats_response(
            max_hp=max_hp,
            min_hp=min_hp,
            max_mana=max_mana,
            min_mana=min_mana,
            max_sta=max_sta,
            min_sta=min_sta,
            gold=gold,
            level=level,
            elu=elu,
            experience=experience,
        )
        await self.connection.send(response)
