"""Tarea para solicitud de atributos del personaje."""

import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class TaskRequestAttributes(Task):
    """Tarea que maneja la solicitud de atributos del personaje."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de solicitud de atributos.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            redis_client: Cliente Redis para obtener atributos.
            session_data: Datos de sesión compartidos (para obtener user_id).
        """
        super().__init__(data, message_sender)
        self.redis_client = redis_client
        self.session_data = session_data

    async def execute(self) -> None:
        """Obtiene atributos desde Redis y los envía al cliente usando PacketID 50."""
        # Primero verificar si hay atributos en sesión (creación de personaje)
        if self.session_data and "dice_attributes" in self.session_data:
            attributes = self.session_data["dice_attributes"]
            logger.info(
                "Enviando atributos desde sesión a %s: %s",
                self.message_sender.connection.address,
                attributes,
            )

            # Intentar con send_attributes (PacketID 50)
            await self.message_sender.send_attributes(
                strength=attributes["strength"],
                agility=attributes["agility"],
                intelligence=attributes["intelligence"],
                charisma=attributes["charisma"],
                constitution=attributes["constitution"],
            )
            return

        # Si no hay en sesión, obtener desde Redis usando user_id
        if not self.redis_client:
            logger.error("Redis no disponible para obtener atributos")
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        if not self.session_data or "user_id" not in self.session_data:
            logger.warning(
                "Cliente %s solicitó atributos pero no hay user_id en sesión",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        # Obtener atributos desde Redis
        user_id = self.session_data["user_id"]
        stats_key = f"player:{user_id}:stats"
        stats_data = await self.redis_client.redis.hgetall(stats_key)  # type: ignore[misc]

        if stats_data:
            strength = int(stats_data.get("strength", 0))
            agility = int(stats_data.get("agility", 0))
            intelligence = int(stats_data.get("intelligence", 0))
            charisma = int(stats_data.get("charisma", 0))
            constitution = int(stats_data.get("constitution", 0))

            logger.info(
                "Enviando atributos desde Redis para user_id %d: "
                "STR=%d AGI=%d INT=%d CHA=%d CON=%d",
                user_id,
                strength,
                agility,
                intelligence,
                charisma,
                constitution,
            )

            # Intentar con send_attributes (PacketID 50)
            await self.message_sender.send_attributes(
                strength=strength,
                agility=agility,
                intelligence=intelligence,
                charisma=charisma,
                constitution=constitution,
            )
        else:
            logger.warning(
                "No se encontraron atributos en Redis para user_id %d",
                user_id,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
