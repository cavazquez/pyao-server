"""Handler para comando de mensaje de chat."""

import logging
import time
from typing import TYPE_CHECKING

from src.command_handlers.accept_clan_handler import AcceptClanCommandHandler
from src.command_handlers.create_clan_handler import CreateClanCommandHandler
from src.command_handlers.demote_clan_member_handler import DemoteClanMemberCommandHandler
from src.command_handlers.invite_clan_handler import InviteClanCommandHandler
from src.command_handlers.kick_clan_member_handler import KickClanMemberCommandHandler
from src.command_handlers.leave_clan_handler import LeaveClanCommandHandler
from src.command_handlers.promote_clan_member_handler import PromoteClanMemberCommandHandler
from src.command_handlers.reject_clan_handler import RejectClanCommandHandler
from src.command_handlers.start_player_trade_handler import StartPlayerTradeCommandHandler
from src.command_handlers.transfer_clan_leadership_handler import (
    TransferClanLeadershipCommandHandler,
)
from src.commands.accept_clan_command import AcceptClanCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.create_clan_command import CreateClanCommand
from src.commands.demote_clan_member_command import DemoteClanMemberCommand
from src.commands.invite_clan_command import InviteClanCommand
from src.commands.kick_clan_member_command import KickClanMemberCommand
from src.commands.leave_clan_command import LeaveClanCommand
from src.commands.promote_clan_member_command import PromoteClanMemberCommand
from src.commands.reject_clan_command import RejectClanCommand
from src.commands.start_player_trade_command import StartPlayerTradeCommand
from src.commands.talk_command import TalkCommand
from src.commands.transfer_clan_leadership_command import TransferClanLeadershipCommand
from src.services.npc.summon_service import MAX_MASCOTAS

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
    """Handler para comando de mensaje de chat (solo lógica de negocio)."""

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
        session_data: dict[str, dict[str, int]] | None = None,
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

        # Comando /METRICS - mostrar métricas de rendimiento
        if command.is_metrics_command():
            await self._handle_metrics_command(user_id)
            return CommandResult.ok(data={"command": "metrics"})

        # Comando /COMERCIAR
        if command.is_trade_command():
            await self._handle_trade_command(user_id, command)
            return CommandResult.ok(data={"command": "trade"})

        # Comandos de clan - procesar antes del broadcast
        if command.is_clan_command():
            await self._handle_clan_command(user_id, command)
            return CommandResult.ok(data={"command": "clan"})

        # Comandos de mascotas - procesar antes del broadcast
        if command.is_pet_command():
            await self._handle_pet_command(user_id, command)
            return CommandResult.ok(data={"command": "pet"})

        # Broadcast multijugador: enviar mensaje a todos los jugadores en el mapa
        if not self.map_manager:
            return CommandResult.error("MapManager no disponible")

        # Obtener el nombre del usuario
        username = "Desconocido"
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        # Obtener el mapa del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return CommandResult.error("No se encontró posición del jugador")

        map_id = position["map"]

        # Formatear mensaje con el nombre del usuario
        formatted_message = f"{username}: {message}"

        # Enviar a todos los jugadores en el mapa (incluyendo el emisor)
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)
        for sender in all_senders:
            await sender.send_console_msg(formatted_message)

        logger.debug(
            "Mensaje de chat de user %d enviado a %d jugadores en mapa %d",
            user_id,
            len(all_senders),
            map_id,
        )

        return CommandResult.ok(
            data={
                "user_id": user_id,
                "username": username,
                "message": message,
                "map_id": map_id,
                "recipients": len(all_senders),
            }
        )

    async def _handle_metrics_command(self, user_id: int) -> None:
        """Maneja el comando /METRICS para mostrar métricas de rendimiento.

        Args:
            user_id: ID del usuario que solicita las métricas.
        """
        if not self.game_tick:
            await self.message_sender.send_console_msg(
                "Métricas no disponibles (GameTick no inicializado)",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return

        # Obtener métricas generales
        metrics = self.game_tick.get_metrics()

        # Construir mensaje de métricas
        lines = [
            "=== MÉTRICAS DE RENDIMIENTO ===",
            f"Total ticks: {metrics['total_ticks']}",
            f"Tiempo promedio: {metrics['avg_tick_time_ms']:.2f}ms",
            f"Tiempo máximo: {metrics['max_tick_time_ms']:.2f}ms",
        ]

        # Métricas por efecto
        if metrics.get("effects"):
            lines.append("\n--- Por Efecto ---")
            for effect_name, effect_metrics in metrics["effects"].items():
                lines.append(
                    f"{effect_name}: {effect_metrics['count']} calls, "
                    f"avg={effect_metrics['avg_time_ms']:.2f}ms, "
                    f"max={effect_metrics['max_time_ms']:.2f}ms"
                )

        # Métricas específicas de NPCMovementEffect
        for effect in self.game_tick.effects:
            if effect.get_name() == "NPCMovement" and hasattr(effect, "get_metrics"):
                npc_metrics = effect.get_metrics()
                lines.extend(
                    (
                        "\n--- NPC Movement ---",
                        f"NPCs procesados: {npc_metrics['total_npcs_processed']}",
                        f"Ticks: {npc_metrics['total_ticks']}",
                        f"Avg tiempo: {npc_metrics['avg_time_ms']:.2f}ms",
                        f"Max tiempo: {npc_metrics['max_time_ms']:.2f}ms",
                        f"NPCs/tick: {npc_metrics['avg_npcs_per_tick']:.2f}",
                    )
                )
                break

        # Enviar métricas línea por línea
        message = "\n".join(lines)
        await self.message_sender.send_multiline_console_msg(message)

        logger.info("Métricas solicitadas por user_id %d", user_id)

    async def _handle_clan_command(self, user_id: int, command: TalkCommand) -> None:  # noqa: PLR0915, PLR0914
        """Maneja comandos de clan desde el chat.

        Args:
            user_id: ID del usuario que ejecuta el comando.
            command: Comando de chat que contiene el comando de clan.
        """
        if not self.clan_service:
            await self.message_sender.send_console_msg(
                "Sistema de clanes no disponible",
                font_color=1,  # FONTTYPE_FIGHT (rojo para errores)
            )
            return

        parsed = command.parse_clan_command()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Comando de clan inválido. Usa /AYUDA para ver comandos disponibles.",
                font_color=1,
            )
            return

        cmd_name, args = parsed

        # Obtener username de la sesión
        username = "Desconocido"
        if "username" in self.session_data:
            username_value = self.session_data["username"]
            if isinstance(username_value, str):
                username = username_value

        try:
            if cmd_name == "CREARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /CREARCLAN <nombre> [descripción]",
                        font_color=1,
                    )
                    return

                clan_name = args[0]
                description = " ".join(args[1:]) if len(args) > 1 else ""

                create_handler = CreateClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                    username=username,
                )
                clan_command = CreateClanCommand(clan_name=clan_name, description=description)
                result = await create_handler.handle(clan_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        f"Clan '{clan_name}' creado exitosamente",
                        font_color=7,  # FONTTYPE_PARTY
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al crear el clan",
                        font_color=1,
                    )

            elif cmd_name == "INVITARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /INVITARCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                invite_handler = InviteClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                invite_command = InviteClanCommand(target_username=target_username)
                result = await invite_handler.handle(invite_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Invitación enviada")
                        if result.data
                        else "Invitación enviada",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al invitar",
                        font_color=1,
                    )

            elif cmd_name == "ACEPTARCLAN":
                accept_handler = AcceptClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                accept_command = AcceptClanCommand()
                result = await accept_handler.handle(accept_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        f"Te uniste al clan '{result.data.get('clan_name', '')}'"
                        if result.data
                        else "Te uniste al clan",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al aceptar invitación",
                        font_color=1,
                    )

            elif cmd_name == "RECHAZARCLAN":
                reject_handler = RejectClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                reject_command = RejectClanCommand()
                result = await reject_handler.handle(reject_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Invitación rechazada")
                        if result.data
                        else "Invitación rechazada",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al rechazar invitación",
                        font_color=1,
                    )

            elif cmd_name == "SALIRCLAN":
                leave_handler = LeaveClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                leave_command = LeaveClanCommand()
                result = await leave_handler.handle(leave_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Abandonaste el clan")
                        if result.data
                        else "Abandonaste el clan",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al abandonar clan",
                        font_color=1,
                    )

            elif cmd_name == "EXPULSARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /EXPULSARCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                kick_handler = KickClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                kick_command = KickClanMemberCommand(target_username=target_username)
                result = await kick_handler.handle(kick_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Miembro expulsado")
                        if result.data
                        else "Miembro expulsado",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al expulsar miembro",
                        font_color=1,
                    )

            elif cmd_name == "PROMOVERCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /PROMOVERCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                promote_handler = PromoteClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                promote_command = PromoteClanMemberCommand(target_username=target_username)
                result = await promote_handler.handle(promote_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Miembro promovido")
                        if result.data
                        else "Miembro promovido",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al promover miembro",
                        font_color=1,
                    )

            elif cmd_name == "DEGRADARCLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /DEGRADARCLAN <usuario>",
                        font_color=1,
                    )
                    return

                target_username = args[0]

                demote_handler = DemoteClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                demote_command = DemoteClanMemberCommand(target_username=target_username)
                result = await demote_handler.handle(demote_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Miembro degradado")
                        if result.data
                        else "Miembro degradado",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al degradar miembro",
                        font_color=1,
                    )

            elif cmd_name == "TRANSFERIRLIDERAZGO":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /TRANSFERIRLIDERAZGO <usuario>",
                        font_color=1,
                    )
                    return

                new_leader_username = args[0]

                transfer_handler = TransferClanLeadershipCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                transfer_command = TransferClanLeadershipCommand(
                    new_leader_username=new_leader_username
                )
                result = await transfer_handler.handle(transfer_command)

                if result.success:
                    await self.message_sender.send_console_msg(
                        result.data.get("message", "Liderazgo transferido")
                        if result.data
                        else "Liderazgo transferido",
                        font_color=7,
                    )
                else:
                    await self.message_sender.send_console_msg(
                        result.error_message or "Error al transferir liderazgo",
                        font_color=1,
                    )

            elif cmd_name == "CLAN":
                if not args:
                    await self.message_sender.send_console_msg(
                        "Uso: /CLAN <mensaje>",
                        font_color=1,
                    )
                    return

                clan_message = " ".join(args)
                error_msg = await self.clan_service.send_clan_message(user_id, clan_message)

                if error_msg:
                    await self.message_sender.send_console_msg(error_msg, font_color=1)
                # Si no hay error, el mensaje ya se envió a todos los miembros

            else:
                await self.message_sender.send_console_msg(
                    f"Comando '{cmd_name}' no reconocido. Usa /AYUDA para ver comandos.",
                    font_color=1,
                )

        except Exception:
            logger.exception("Error al procesar comando de clan")
            await self.message_sender.send_console_msg(
                "Error interno al procesar comando de clan",
                font_color=1,
            )

    async def _handle_trade_command(self, user_id: int, command: TalkCommand) -> None:
        """Maneja el comando /COMERCIAR."""
        if not self.trade_service:
            await self.message_sender.send_console_msg(
                "El sistema de comercio entre jugadores no está disponible.",
                font_color=1,
            )
            return

        parsed = command.parse_trade_command()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Uso: /COMERCIAR <usuario>",
                font_color=1,
            )
            return

        _, args = parsed
        if not args:
            await self.message_sender.send_console_msg(
                "Uso: /COMERCIAR <usuario>",
                font_color=1,
            )
            return

        target_username = args[0]
        trade_handler = StartPlayerTradeCommandHandler(
            trade_service=self.trade_service,
            message_sender=self.message_sender,
        )
        trade_command = StartPlayerTradeCommand(
            initiator_id=user_id,
            target_username=target_username,
        )
        await trade_handler.handle(trade_command)

    async def _handle_pet_command(self, user_id: int, command: TalkCommand) -> None:
        """Maneja los comandos relacionados con mascotas.

        Args:
            user_id: ID del usuario.
            command: Comando de chat.
        """
        if not self.summon_service or not self.npc_service:
            await self.message_sender.send_console_msg(
                "El sistema de mascotas no está disponible.",
                font_color=1,
            )
            return

        parsed = command.parse_pet_command()
        if not parsed:
            await self.message_sender.send_console_msg(
                "Uso: /PET [LIBERAR|INFO]",
                font_color=1,
            )
            return

        _, args = parsed

        # Obtener todas las mascotas del jugador
        all_npcs = await self.npc_service.npc_repository.get_all_npcs()
        player_pets = [
            npc for npc in all_npcs if npc.summoned_by_user_id == user_id and npc.summoned_until > 0
        ]

        # Comando sin argumentos o con "INFO" - mostrar información
        if not args or (args and args[0].upper() == "INFO"):
            if not player_pets:
                await self.message_sender.send_console_msg(
                    "No tienes mascotas invocadas.",
                    font_color=7,
                )
                return

            current_time = time.time()

            pet_info_lines = [f"--- Mascotas ({len(player_pets)}/{MAX_MASCOTAS}) ---"]

            for i, pet in enumerate(player_pets, start=1):
                time_remaining = max(0, int(pet.summoned_until - current_time))
                minutes = time_remaining // 60
                seconds = time_remaining % 60
                pet_info_lines.append(
                    f"{i}. {pet.name} (HP: {pet.hp}/{pet.max_hp}) - Expira en {minutes}m {seconds}s"
                )

            await self.message_sender.send_multiline_console_msg("\n".join(pet_info_lines))
            return

        # Comando "LIBERAR" - liberar todas las mascotas
        if args and args[0].upper() == "LIBERAR":
            if not player_pets:
                await self.message_sender.send_console_msg(
                    "No tienes mascotas para liberar.",
                    font_color=7,
                )
                return

            released_count = 0
            for pet in player_pets:
                try:
                    await self.npc_service.remove_npc(pet)
                    released_count += 1
                    logger.info(
                        "Mascota liberada por comando: user_id=%d, mascota=%s",
                        user_id,
                        pet.name,
                    )
                except Exception:
                    logger.exception(
                        "Error al liberar mascota %s para user_id %d",
                        pet.instance_id,
                        user_id,
                    )

            if released_count > 0:
                await self.message_sender.send_console_msg(
                    f"Has liberado {released_count} mascota(s).",
                    font_color=7,
                )
            else:
                await self.message_sender.send_console_msg(
                    "No se pudieron liberar las mascotas.",
                    font_color=1,
                )
            return

        # Comando desconocido
        await self.message_sender.send_console_msg(
            "Uso: /PET [LIBERAR|INFO]",
            font_color=1,
        )
