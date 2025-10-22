"""Message sender para mensajes de combate (daño, golpes).

Este módulo maneja los mensajes de combate que se envían mediante MULTI_MESSAGE:
- NPCHitUser: Cuando un NPC golpea al jugador
- UserHitNPC: Cuando el jugador golpea a un NPC

Basado en el protocolo del cliente Godot y servidor VB6 original.
"""

import random
from typing import TYPE_CHECKING

from src.models.body_part import BodyPart
from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection


class CombatMessageSender:
    """Sender para mensajes de combate."""

    def __init__(self, connection: "ClientConnection") -> None:  # noqa: UP037
        """Inicializa el sender de mensajes de combate.

        Args:
            connection: Conexión del cliente.
        """
        self.connection = connection

    async def send_npc_hit_user(self, damage: int, body_part: BodyPart | None = None) -> None:
        """Envía mensaje cuando un NPC golpea al jugador.

        Este mensaje se envía mediante MULTI_MESSAGE con índice NPCHitUser (12).
        El cliente muestra un mensaje específico según la parte del cuerpo golpeada.

        Args:
            damage: Cantidad de daño infligido.
            body_part: Parte del cuerpo golpeada. Si es None, se elige aleatoriamente.
        """
        # Si no se especifica parte del cuerpo, elegir aleatoriamente
        if body_part is None:
            body_part = random.choice(list(BodyPart))  # noqa: S311

        # Índice del mensaje NPCHitUser (12, no 13 - enum en Godot empieza en 0)
        message_index = 12

        packet = (
            PacketBuilder()
            .add_byte(ServerPacketID.MULTI_MESSAGE)
            .add_byte(message_index)  # NPCHitUser
            .add_byte(body_part)  # Parte del cuerpo (1-6)
            .add_int16(damage)  # Daño infligido
            .to_bytes()
        )

        await self.connection.send(packet)

    async def send_user_hit_npc(self, damage: int) -> None:
        """Envía mensaje cuando el jugador golpea a un NPC.

        Este mensaje se envía mediante MULTI_MESSAGE con índice UserHitNPC (13).
        El cliente muestra: "¡¡Le has pegado a la criatura por {damage}!!"

        Args:
            damage: Cantidad de daño infligido al NPC.
        """
        # Índice del mensaje UserHitNPC (13, no 14 - enum en Godot empieza en 0)
        message_index = 13

        packet = (
            PacketBuilder()
            .add_byte(ServerPacketID.MULTI_MESSAGE)
            .add_byte(message_index)  # UserHitNPC
            .add_int32(damage)  # Daño infligido (int32)
            .to_bytes()
        )

        await self.connection.send(packet)

    async def send_npc_hit_user_head(self, damage: int) -> None:
        """Envía mensaje cuando un NPC golpea la cabeza del jugador.

        Args:
            damage: Cantidad de daño infligido.
        """
        await self.send_npc_hit_user(damage, BodyPart.HEAD)

    async def send_npc_hit_user_torso(self, damage: int) -> None:
        """Envía mensaje cuando un NPC golpea el torso del jugador.

        Args:
            damage: Cantidad de daño infligido.
        """
        await self.send_npc_hit_user(damage, BodyPart.TORSO)

    async def send_npc_hit_user_left_arm(self, damage: int) -> None:
        """Envía mensaje cuando un NPC golpea el brazo izquierdo del jugador.

        Args:
            damage: Cantidad de daño infligido.
        """
        await self.send_npc_hit_user(damage, BodyPart.LEFT_ARM)

    async def send_npc_hit_user_right_arm(self, damage: int) -> None:
        """Envía mensaje cuando un NPC golpea el brazo derecho del jugador.

        Args:
            damage: Cantidad de daño infligido.
        """
        await self.send_npc_hit_user(damage, BodyPart.RIGHT_ARM)

    async def send_npc_hit_user_left_leg(self, damage: int) -> None:
        """Envía mensaje cuando un NPC golpea la pierna izquierda del jugador.

        Args:
            damage: Cantidad de daño infligido.
        """
        await self.send_npc_hit_user(damage, BodyPart.LEFT_LEG)

    async def send_npc_hit_user_right_leg(self, damage: int) -> None:
        """Envía mensaje cuando un NPC golpea la pierna derecha del jugador.

        Args:
            damage: Cantidad de daño infligido.
        """
        await self.send_npc_hit_user(damage, BodyPart.RIGHT_LEG)
