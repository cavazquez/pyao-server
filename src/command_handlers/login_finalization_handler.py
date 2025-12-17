"""Handler especializado para finalización del proceso de login."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.motd_handler import MotdCommandHandler
from src.commands.motd_command import MotdCommand
from src.services.player.player_service import PlayerService

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class LoginFinalizationHandler:
    """Handler especializado para finalización del proceso de login."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        equipment_repo: EquipmentRepository | None,
        server_repo: ServerRepository | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de finalización.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            equipment_repo: Repositorio de equipamiento.
            server_repo: Repositorio del servidor para obtener el MOTD.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.equipment_repo = equipment_repo
        self.server_repo = server_repo
        self.message_sender = message_sender
        self._motd_handler: MotdCommandHandler | None = None

    async def finalize_login(self, user_id: int) -> None:
        """Finaliza el proceso de login.

        Args:
            user_id: ID del usuario.
        """
        logger.info("[LOGIN-FINALIZE] user_id=%d Iniciando finalización de login", user_id)

        # Enviar inventario
        logger.info("[LOGIN-FINALIZE] user_id=%d Enviando inventario", user_id)
        player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
        await player_service.send_inventory(user_id, self.equipment_repo)

        # Habilitar botón de party en el cliente (después del spawn completo)
        logger.info("[LOGIN-FINALIZE] user_id=%d Enviando SHOW_PARTY_FORM (ID=101)", user_id)
        await self.message_sender.send_show_party_form()

        # NOTA: El envío de CLAN_DETAILS (packet 80) está deshabilitado hasta que el cliente
        # Godot implemente el handler para procesar GuildDetails.
        # Ver: docs/CLAN_BUTTON_ENABLING.md para instrucciones de cómo habilitarlo.

        # Enviar MOTD (Mensaje del Día)
        logger.info("[LOGIN-FINALIZE] user_id=%d Enviando MOTD", user_id)
        if self._motd_handler is None:
            self._motd_handler = MotdCommandHandler(
                server_repo=self.server_repo,
                message_sender=self.message_sender,
            )

        motd_command = MotdCommand()
        await self._motd_handler.handle(motd_command)

        logger.info("[LOGIN-FINALIZE] user_id=%d Login finalizado correctamente", user_id)
