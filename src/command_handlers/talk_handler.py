"""Handler para comando de mensaje de chat."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.talk_clan_handler import TalkClanHandler
from src.command_handlers.talk_metrics_handler import TalkMetricsHandler
from src.command_handlers.talk_pet_handler import TalkPetHandler
from src.command_handlers.talk_public_handler import TalkPublicHandler
from src.command_handlers.talk_trade_handler import TalkTradeHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.talk_command import TalkCommand

if TYPE_CHECKING:
    from src.game.game_tick import GameTick
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.clan_service import ClanService
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService
    from src.services.trade_service import TradeService

logger = logging.getLogger(__name__)


class TalkCommandHandler(CommandHandler):
    """Handler para comando de mensaje de chat (solo lógica de negocio).

    Este handler delega a handlers especializados según el tipo de comando:
    - TalkMetricsHandler: Comandos de métricas
    - TalkTradeHandler: Comandos de comercio
    - TalkClanHandler: Comandos de clan
    - TalkPetHandler: Comandos de mascotas
    - TalkPublicHandler: Mensajes de chat público
    """

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        map_manager: MapManager | None,
        game_tick: GameTick | None,
        message_sender: MessageSender,
        clan_service: ClanService | None = None,
        trade_service: TradeService | None = None,
        npc_service: NPCService | None = None,
        summon_service: SummonService | None = None,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            game_tick: Sistema de GameTick para comandos de métricas.
            message_sender: Enviador de mensajes.
            clan_service: Servicio de clanes (opcional).
            trade_service: Servicio de comercio entre jugadores (opcional).
            npc_service: Servicio de NPCs (opcional, para comandos de mascotas).
            summon_service: Servicio de invocación (opcional, para comandos de mascotas).
            session_data: Datos de sesión compartidos.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.game_tick = game_tick
        self.message_sender = message_sender
        self.clan_service = clan_service
        self.trade_service = trade_service
        self.npc_service = npc_service
        self.summon_service = summon_service
        self.session_data = session_data or {}

        # Inicializar handlers especializados
        self.metrics_handler = TalkMetricsHandler(
            game_tick=game_tick,
            message_sender=message_sender,
        )

        self.trade_handler = TalkTradeHandler(
            trade_service=trade_service,
            message_sender=message_sender,
        )

        self.clan_handler = TalkClanHandler(
            clan_service=clan_service,
            message_sender=message_sender,
            session_data=session_data,
        )

        self.pet_handler = TalkPetHandler(
            npc_service=npc_service,
            summon_service=summon_service,
            message_sender=message_sender,
        )

        self.public_handler = TalkPublicHandler(
            player_repo=player_repo,
            map_manager=map_manager,
            message_sender=message_sender,
            session_data=session_data,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de mensaje de chat (solo lógica de negocio).

        Args:
            command: Comando de mensaje de chat.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, TalkCommand):
            return CommandResult.error("Comando inválido: se esperaba TalkCommand")

        user_id = command.user_id
        message = command.message

        logger.info("TalkCommandHandler: mensaje de chat de user_id %d: %s", user_id, message)

        # Comando /METRICS - delegar a handler especializado
        if command.is_metrics_command():
            await self.metrics_handler.handle_metrics_command(user_id)
            return CommandResult.ok(data={"command": "metrics"})

        # Comando /COMERCIAR - delegar a handler especializado
        if command.is_trade_command():
            await self.trade_handler.handle_trade_command(user_id, command)
            return CommandResult.ok(data={"command": "trade"})

        # Comandos de clan - delegar a handler especializado
        if command.is_clan_command():
            await self.clan_handler.handle_clan_command(user_id, command)
            return CommandResult.ok(data={"command": "clan"})

        # Comandos de mascotas - delegar a handler especializado
        if command.is_pet_command():
            await self.pet_handler.handle_pet_command(user_id, command)
            return CommandResult.ok(data={"command": "pet"})

        # Mensaje de chat público - delegar a handler especializado
        success, error_message, data = await self.public_handler.handle_public_message(
            user_id, message
        )

        if not success:
            return CommandResult.error(error_message or "Error al enviar mensaje")

        return CommandResult.ok(data=data)
