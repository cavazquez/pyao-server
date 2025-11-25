"""Handler para comando de Game Master."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.gm_command import GMCommand

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.player_map_service import PlayerMapService

logger = logging.getLogger(__name__)


class GMCommandHandler(CommandHandler):
    """Handler para comando de Game Master (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        player_map_service: PlayerMapService,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas (para verificar GM).
            player_map_service: Servicio de mapas de jugador.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.player_map_service = player_map_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de Game Master (solo lógica de negocio).

        Args:
            command: Comando de Game Master.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, GMCommand):
            return CommandResult.error("Comando inválido: se esperaba GMCommand")

        user_id = command.user_id

        # Verificar permisos de GM
        is_gm = await self.account_repo.is_gm_by_user_id(user_id)
        if not is_gm:
            logger.warning("Intento de comando GM por usuario no autorizado: user_id=%d", user_id)
            await self.message_sender.send_console_msg(
                "No tienes permisos de Game Master.",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return CommandResult.error("No tienes permisos de Game Master")

        subcommand = command.subcommand
        username = command.username
        map_id = command.map_id
        x = command.x
        y = command.y

        logger.info(
            "GMCommandHandler: user_id=%d (GM), subcommand=%d, username='%s', map=%d, pos=(%d,%d)",
            user_id,
            subcommand,
            username,
            map_id,
            x,
            y,
        )

        # Si el username es "YO" o está vacío, teletransportar al propio jugador
        if command.is_self_teleport():
            return await self._teleport_player(user_id, map_id, x, y)
        # TODO: Implementar teletransporte de otros jugadores (requiere buscar por username)
        await self.message_sender.send_console_msg(
            "Teletransporte de otros jugadores no implementado aún."
        )
        logger.info("Teletransporte de otros jugadores no implementado: %s", username)
        return CommandResult.error("Teletransporte de otros jugadores no implementado")

    async def _teleport_player(
        self, user_id: int, new_map: int, new_x: int, new_y: int
    ) -> CommandResult:
        """Teletransporta un jugador a una nueva posición.

        Args:
            user_id: ID del jugador.
            new_map: ID del nuevo mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.

        Returns:
            Resultado de la ejecución.
        """
        # Obtener posición actual
        position = await self.player_repo.get_position(user_id)
        if position is None:
            logger.warning("No se encontró posición para user_id %d", user_id)
            return CommandResult.error("No se encontró posición del jugador")

        current_map = position["map"]
        current_x = position["x"]
        current_y = position["y"]
        current_heading = position.get("heading", 3)

        # Si es el mismo mapa, usar teleport_in_same_map
        if current_map == new_map:
            await self.player_map_service.teleport_in_same_map(
                user_id=user_id,
                map_id=current_map,
                old_x=current_x,
                old_y=current_y,
                new_x=new_x,
                new_y=new_y,
                heading=current_heading,
                message_sender=self.message_sender,
            )
        # Cambio de mapa - usar transition_to_map
        else:
            await self.player_map_service.transition_to_map(
                user_id=user_id,
                current_map=current_map,
                current_x=current_x,
                current_y=current_y,
                new_map=new_map,
                new_x=new_x,
                new_y=new_y,
                heading=current_heading,
                message_sender=self.message_sender,
            )

        logger.info(
            "Jugador %d teletransportado de (%d, %d, %d) a (%d, %d, %d)",
            user_id,
            current_map,
            current_x,
            current_y,
            new_map,
            new_x,
            new_y,
        )

        return CommandResult.ok(
            data={
                "user_id": user_id,
                "from_map": current_map,
                "from_x": current_x,
                "from_y": current_y,
                "to_map": new_map,
                "to_x": new_x,
                "to_y": new_y,
            }
        )
