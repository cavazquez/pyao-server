"""Tarea para solicitud de atributos del personaje."""

import logging
from typing import TYPE_CHECKING

from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskRequestAttributes(Task):
    """Tarea que maneja la solicitud de atributos del personaje."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de solicitud de atributos.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores para obtener atributos.
            session_data: Datos de sesión compartidos (para obtener user_id).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
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

        # Si no hay en sesión, obtener desde repositorio usando user_id
        if not self.player_repo:
            logger.error("PlayerRepository no disponible para obtener atributos")
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        if not self.session_data or "user_id" not in self.session_data:
            logger.warning(
                "Cliente %s solicitó atributos pero no hay user_id en sesión",
                self.message_sender.connection.address,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        # Obtener atributos desde el repositorio
        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
            return

        user_id = int(user_id_value)
        attributes = await self.player_repo.get_attributes(user_id)

        if attributes is not None:
            logger.info(
                "Enviando atributos desde repositorio para user_id %d: "
                "STR=%d AGI=%d INT=%d CHA=%d CON=%d",
                user_id,
                attributes["strength"],
                attributes["agility"],
                attributes["intelligence"],
                attributes["charisma"],
                attributes["constitution"],
            )

            await self.message_sender.send_attributes(
                strength=attributes["strength"],
                agility=attributes["agility"],
                intelligence=attributes["intelligence"],
                charisma=attributes["charisma"],
                constitution=attributes["constitution"],
            )
        else:
            logger.warning(
                "No se encontraron atributos en repositorio para user_id %d",
                user_id,
            )
            await self.message_sender.send_attributes(0, 0, 0, 0, 0)
