"""Handler para comando de Game Master."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.gm_command import GMCommand
from src.utils.gold_atomic import operation_id

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.action_cadence import ActionCadence
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
        action_cadence: ActionCadence | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas (para verificar GM).
            player_map_service: Servicio de mapas de jugador.
            message_sender: Enviador de mensajes.
            action_cadence: Reserva compartida con el movimiento del jugador.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.player_map_service = player_map_service
        self.message_sender = message_sender
        self.action_cadence = action_cadence

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
        return await self._teleport_other(command)

    async def _teleport_other(self, command: GMCommand) -> CommandResult:
        """Resuelve el objetivo por su cuenta y conserva la conexión del objetivo.

        Returns:
            Rechazo sin efectos o transición confirmada con el pipeline normal.
        """
        maps = self.player_map_service.map_manager
        target = maps.find_player_by_username(command.username)
        account = await self.account_repo.get_account_by_user_id(target) if target else None
        sender = maps.get_player_message_sender(target) if target else None
        if (
            target is None
            or account is None
            or sender is None
            or not sender.connection.is_authenticated
            or account.get("username", "").casefold() != command.username.casefold()
        ):
            return CommandResult.error(
                "El jugador objetivo no está conectado o su identidad no es válida"
            )
        if not maps.has_map(command.map_id) or not maps.can_move_to(
            command.map_id, command.x, command.y
        ):
            return CommandResult.error("El mapa o destino no está disponible")
        if self.action_cadence and not self.action_cadence.claim(target, "walk"):
            return CommandResult.error("El jugador está moviéndose; reintentá en un instante")
        reservation = operation_id()
        try:
            maps.reserve_positions(reservation, command.map_id, [(command.x, command.y)])
            return await self._teleport_player(
                target, command.map_id, command.x, command.y, sender=sender
            )
        except ValueError:
            return CommandResult.error("El destino cambió y ya no está disponible")
        finally:
            maps.release_positions(reservation)
            if self.action_cadence:
                self.action_cadence.release(target, "walk")

    async def _teleport_player(
        self,
        user_id: int,
        new_map: int,
        new_x: int,
        new_y: int,
        *,
        sender: MessageSender | None = None,
    ) -> CommandResult:
        """Teletransporta un jugador a una nueva posición.

        Args:
            user_id: ID del jugador.
            new_map: ID del nuevo mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            sender: Emisor del objetivo; por defecto el propio jugador.

        Returns:
            Resultado de la ejecución.
        """
        destination_sender = sender or self.message_sender
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
            applied = await self.player_map_service.teleport_in_same_map(
                user_id=user_id,
                map_id=current_map,
                old_x=current_x,
                old_y=current_y,
                new_x=new_x,
                new_y=new_y,
                heading=current_heading,
                message_sender=destination_sender,
            )
        # Cambio de mapa - usar transition_to_map
        else:
            applied = await self.player_map_service.transition_to_map(
                user_id=user_id,
                current_map=current_map,
                current_x=current_x,
                current_y=current_y,
                new_map=new_map,
                new_x=new_x,
                new_y=new_y,
                heading=current_heading,
                message_sender=destination_sender,
            )

        if not applied:
            return CommandResult.error("La llegada fue rechazada; conservas tu posición.")

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
