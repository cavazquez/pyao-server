"""Handler para comando de cambio de dirección."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.change_heading_command import ChangeHeadingCommand

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Body que representa una barca en el cliente Godot (incluido en Consts.ShipIds)
SHIP_BODY_ID = 84


class ChangeHeadingCommandHandler(CommandHandler):
    """Handler para comando de cambio de dirección (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository | None,
        map_manager: MapManager | None,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.message_sender = message_sender
        self.session_data = session_data or {}

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de cambio de dirección (solo lógica de negocio).

        Args:
            command: Comando de cambio de dirección.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, ChangeHeadingCommand):
            return CommandResult.error("Comando inválido: se esperaba ChangeHeadingCommand")

        user_id = command.user_id
        heading = command.heading

        logger.info("ChangeHeadingCommandHandler: user %d cambió dirección a %d", user_id, heading)

        # Guardar la dirección en Redis
        await self.player_repo.set_heading(user_id, heading)

        # Determinar apariencia visual según si está navegando o no
        char_body = 1  # Valor por defecto
        char_head = 15  # Valor por defecto

        # Si el jugador está navegando, usar siempre el body de barco y sin cabeza
        is_sailing = await self.player_repo.is_sailing(user_id)
        if is_sailing:
            char_body = SHIP_BODY_ID
            char_head = 0
        elif self.account_repo and "username" in self.session_data:
            username = self.session_data["username"]
            if isinstance(username, str):
                account_data = await self.account_repo.get_account(username)
                if account_data:
                    char_body = int(account_data.get("char_race", 1))
                    char_head = int(account_data.get("char_head", 15))
                    # Si body es 0, usar valor por defecto
                    if char_body == 0:
                        char_body = 1

        # Enviar CHARACTER_CHANGE de vuelta al cliente para confirmar
        await self.message_sender.send_character_change(
            char_index=user_id,
            body=char_body,
            head=char_head,
            heading=heading,
        )

        # Broadcast multijugador: enviar CHARACTER_CHANGE a otros jugadores en el mapa
        if self.map_manager:
            # Obtener el mapa actual del jugador
            position = await self.player_repo.get_position(user_id)
            if position:
                map_id = position["map"]

                # Enviar CHARACTER_CHANGE a todos los demás jugadores en el mapa
                other_senders = self.map_manager.get_all_message_senders_in_map(
                    map_id, exclude_user_id=user_id
                )
                for sender in other_senders:
                    await sender.send_character_change(
                        char_index=user_id,
                        body=char_body,
                        head=char_head,
                        heading=heading,
                    )

                logger.debug(
                    "Cambio de dirección de user %d notificado a %d jugadores en mapa %d",
                    user_id,
                    len(other_senders),
                    map_id,
                )

        return CommandResult.ok(
            data={
                "user_id": user_id,
                "heading": heading,
                "char_body": char_body,
                "char_head": char_head,
            }
        )
