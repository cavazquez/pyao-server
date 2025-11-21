"""Tarea para mensajes de chat."""

import logging
from typing import TYPE_CHECKING

from src.network.packet_data import TalkData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.game.game_tick import GameTick
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes
MIN_TALK_PACKET_SIZE = 3  # PacketID + int16
MAX_MESSAGE_LENGTH = 255  # Longitud máxima del mensaje de chat


class TaskTalk(Task):
    """Tarea para procesar mensajes de chat del jugador."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        account_repo: AccountRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        game_tick: GameTick | None = None,
    ) -> None:
        """Inicializa la tarea Talk.

        Args:
            data: Datos del paquete recibido.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas para broadcast.
            session_data: Datos de sesión del cliente.
            game_tick: Sistema de GameTick para comandos de métricas (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.session_data = session_data
        self.game_tick = game_tick

    def _parse_packet(self) -> TalkData | None:
        """Parsea el paquete Talk.

        Formato: PacketID (1 byte) + longitud (int16) + mensaje (string UTF-8)

        Returns:
            TalkData con el mensaje validado o None si el paquete es inválido.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        # Usar nueva API consistente
        message_result = validator.validate_string(
            min_length=1, max_length=MAX_MESSAGE_LENGTH, encoding="utf-8"
        )

        if not message_result.success:
            return None

        return TalkData(message=message_result.data or "")

    async def execute(self) -> None:
        """Procesa el mensaje de chat."""
        talk_data = self._parse_packet()

        if talk_data is None:
            logger.warning(
                "Paquete Talk inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)

        if user_id is None:
            logger.warning(
                "Mensaje de chat recibido sin sesión activa desde %s",
                self.message_sender.connection.address,
            )
            return

        logger.info(
            "Mensaje de chat de user_id %d: %s",
            user_id,
            talk_data.message,
        )

        # Convertir user_id a int
        if isinstance(user_id, dict):
            return

        user_id_int = int(user_id)

        # Comando /METRICS - mostrar métricas de rendimiento
        if talk_data.message.upper().startswith("/METRICS"):
            await self._handle_metrics_command(user_id_int)
            return

        # Broadcast multijugador: enviar mensaje a todos los jugadores en el mapa
        if self.map_manager and self.player_repo and self.account_repo and self.session_data:
            # Obtener el nombre del usuario
            username = "Desconocido"
            if "username" in self.session_data:
                username_value = self.session_data["username"]
                if isinstance(username_value, str):
                    username = username_value

            # Obtener el mapa del jugador
            position = await self.player_repo.get_position(user_id_int)
            if position:
                map_id = position["map"]

                # Formatear mensaje con el nombre del usuario
                formatted_message = f"{username}: {talk_data.message}"

                # Enviar a todos los jugadores en el mapa (incluyendo el emisor)
                all_senders = self.map_manager.get_all_message_senders_in_map(map_id)
                for sender in all_senders:
                    await sender.send_console_msg(formatted_message)

                logger.debug(
                    "Mensaje de chat de user %d enviado a %d jugadores en mapa %d",
                    user_id_int,
                    len(all_senders),
                    map_id,
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
