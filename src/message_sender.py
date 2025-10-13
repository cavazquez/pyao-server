"""Envío de mensajes específicos al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import (
    build_attributes_response,
    build_change_map_response,
    build_character_create_response,
    build_dice_roll_response,
    build_error_msg_response,
    build_logged_response,
    build_pos_update_response,
    build_update_hp_response,
    build_update_hunger_and_thirst_response,
    build_update_mana_response,
    build_update_sta_response,
    build_update_user_stats_response,
    build_user_char_index_in_server_response,
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
        """Envía paquete Logged del protocolo AO estándar.

        Args:
            user_class: Clase del personaje (1 byte).
        """
        response = build_logged_response(user_class=user_class)
        logger.info("[%s] Enviando LOGGED: userClass=%d", self.connection.address, user_class)
        await self.connection.send(response)

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

    async def send_user_char_index_in_server(self, char_index: int) -> None:
        """Envía paquete UserCharIndexInServer del protocolo AO estándar.

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

    async def send_error_msg(self, error_message: str) -> None:
        """Envía paquete ErrorMsg del protocolo AO estándar.

        Args:
            error_message: Mensaje de error.
        """
        response = build_error_msg_response(error_message=error_message)
        logger.info("[%s] Enviando ERROR_MSG: %s", self.connection.address, error_message)
        await self.connection.send(response)

    async def send_update_hp(self, hp: int) -> None:
        """Envía paquete UpdateHP del protocolo AO estándar.

        Args:
            hp: Puntos de vida actuales (int16).
        """
        response = build_update_hp_response(hp=hp)
        logger.info("[%s] Enviando UPDATE_HP: %d", self.connection.address, hp)
        await self.connection.send(response)

    async def send_update_mana(self, mana: int) -> None:
        """Envía paquete UpdateMana del protocolo AO estándar.

        Args:
            mana: Puntos de mana actuales (int16).
        """
        response = build_update_mana_response(mana=mana)
        logger.info("[%s] Enviando UPDATE_MANA: %d", self.connection.address, mana)
        await self.connection.send(response)

    async def send_update_sta(self, stamina: int) -> None:
        """Envía paquete UpdateSta del protocolo AO estándar.

        Args:
            stamina: Puntos de stamina actuales (int16).
        """
        response = build_update_sta_response(stamina=stamina)
        logger.info("[%s] Enviando UPDATE_STA: %d", self.connection.address, stamina)
        await self.connection.send(response)

    async def send_update_hunger_and_thirst(
        self, max_water: int, min_water: int, max_hunger: int, min_hunger: int
    ) -> None:
        """Envía paquete UpdateHungerAndThirst del protocolo AO estándar.

        Args:
            max_water: Sed máxima (u8).
            min_water: Sed actual (u8).
            max_hunger: Hambre máxima (u8).
            min_hunger: Hambre actual (u8).
        """
        response = build_update_hunger_and_thirst_response(
            max_water=max_water,
            min_water=min_water,
            max_hunger=max_hunger,
            min_hunger=min_hunger,
        )
        logger.info(
            "[%s] Enviando UPDATE_HUNGER_AND_THIRST: water=%d/%d hunger=%d/%d",
            self.connection.address,
            min_water,
            max_water,
            min_hunger,
            max_hunger,
        )
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
        logger.info(
            "[%s] Enviando UPDATE_USER_STATS: HP=%d/%d MANA=%d/%d STA=%d/%d "
            "GOLD=%d LVL=%d ELU=%d EXP=%d",
            self.connection.address,
            min_hp,
            max_hp,
            min_mana,
            max_mana,
            min_sta,
            max_sta,
            gold,
            level,
            elu,
            experience,
        )
        await self.connection.send(response)

    async def send_character_create(  # noqa: PLR0913, PLR0917
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
    ) -> None:
        """Envía paquete CharacterCreate del protocolo AO estándar.

        Args:
            char_index: Índice del personaje (int16).
            body: ID del cuerpo/raza (int16).
            head: ID de la cabeza (int16).
            heading: Dirección que mira el personaje (byte).
            x: Posición X (byte).
            y: Posición Y (byte).
            weapon: ID del arma equipada (int16), por defecto 0.
            shield: ID del escudo equipado (int16), por defecto 0.
            helmet: ID del casco equipado (int16), por defecto 0.
            fx: ID del efecto visual (int16), por defecto 0.
            loops: Loops del efecto (int16), por defecto 0.
            name: Nombre del personaje (string), por defecto vacío.
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
        )
        logger.info(
            "[%s] Enviando CHARACTER_CREATE: charIndex=%d body=%d head=%d heading=%d "
            "pos=(%d,%d) name=%s",
            self.connection.address,
            char_index,
            body,
            head,
            heading,
            x,
            y,
            name,
        )
        await self.connection.send(response)
