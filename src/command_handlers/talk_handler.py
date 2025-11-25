"""Handler para comando de mensaje de chat."""

import logging
from typing import TYPE_CHECKING

from src.command_handlers.accept_clan_handler import AcceptClanCommandHandler
from src.command_handlers.create_clan_handler import CreateClanCommandHandler
from src.command_handlers.invite_clan_handler import InviteClanCommandHandler
from src.command_handlers.kick_clan_member_handler import KickClanMemberCommandHandler
from src.command_handlers.leave_clan_handler import LeaveClanCommandHandler
from src.command_handlers.reject_clan_handler import RejectClanCommandHandler
from src.commands.accept_clan_command import AcceptClanCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.create_clan_command import CreateClanCommand
from src.commands.invite_clan_command import InviteClanCommand
from src.commands.kick_clan_member_command import KickClanMemberCommand
from src.commands.leave_clan_command import LeaveClanCommand
from src.commands.reject_clan_command import RejectClanCommand
from src.commands.talk_command import TalkCommand

if TYPE_CHECKING:
    from src.game.game_tick import GameTick
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.clan_service import ClanService

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
            session_data: Datos de sesión compartidos.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.game_tick = game_tick
        self.message_sender = message_sender
        self.clan_service = clan_service
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

        # Comandos de clan - procesar antes del broadcast
        if command.is_clan_command():
            await self._handle_clan_command(user_id, command)
            return CommandResult.ok(data={"command": "clan"})

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

                handler = CreateClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                    username=username,
                )
                clan_command = CreateClanCommand(clan_name=clan_name, description=description)
                result = await handler.handle(clan_command)

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

                handler = InviteClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                invite_command = InviteClanCommand(target_username=target_username)
                result = await handler.handle(invite_command)

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
                handler = AcceptClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                accept_command = AcceptClanCommand()
                result = await handler.handle(accept_command)

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
                handler = RejectClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                reject_command = RejectClanCommand()
                result = await handler.handle(reject_command)

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
                handler = LeaveClanCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                leave_command = LeaveClanCommand()
                result = await handler.handle(leave_command)

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

                handler = KickClanMemberCommandHandler(
                    clan_service=self.clan_service,
                    user_id=user_id,
                )
                kick_command = KickClanMemberCommand(target_username=target_username)
                result = await handler.handle(kick_command)

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

            else:
                await self.message_sender.send_console_msg(
                    f"Comando '{cmd_name}' no reconocido. Usa /AYUDA para ver comandos disponibles.",
                    font_color=1,
                )

        except Exception:
            logger.exception("Error al procesar comando de clan")
            await self.message_sender.send_console_msg(
                "Error interno al procesar comando de clan",
                font_color=1,
            )
