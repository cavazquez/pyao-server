"""Task para manejar ataques de jugadores."""

import logging
from typing import TYPE_CHECKING

from src.commands.attack_command import AttackCommand
from src.network.packet_reader import PacketReader
from src.network.session_manager import SessionManager
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.command_handlers.attack_handler import AttackCommandHandler
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TaskAttack(Task):
    """Maneja el packet ATTACK del cliente.

    Usa Command Pattern: solo hace parsing y delega la lógica de negocio al handler.
    """

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        attack_handler: AttackCommandHandler | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el task.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            attack_handler: Handler para ejecutar el comando de ataque.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.attack_handler = attack_handler
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el ataque del jugador (solo parsing y delegación).

        Usa Command Pattern: parsea el packet, crea el comando y delega al handler.
        """
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de atacar sin estar logueado")
            return

        # Validar que tenemos el handler
        if not self.attack_handler:
            logger.error("AttackCommandHandler no disponible")
            return

        # Obtener posición del jugador para calcular objetivo
        # Necesitamos esto para crear el comando
        # Nota: Esto podría moverse al handler, pero necesitamos la posición para el comando
        # Por ahora lo dejamos aquí para mantener la separación de responsabilidades

        # Obtener player_repo del handler (tiene acceso a todas las dependencias)
        player_repo = self.attack_handler.player_repo
        position = await player_repo.get_position(user_id)
        if not position:
            logger.error("No se encontró posición para user_id %d", user_id)
            return

        player_x = position["x"]
        player_y = position["y"]
        player_map = position["map"]
        player_heading = position["heading"]

        # Calcular posición del objetivo según la dirección
        target_x, target_y = self._get_target_position(player_x, player_y, player_heading)

        # Crear comando (solo datos)
        command = AttackCommand(
            user_id=user_id,
            target_x=target_x,
            target_y=target_y,
            map_id=player_map,
        )

        # Delegar al handler (separación de responsabilidades)
        result = await self.attack_handler.handle(command)

        # Manejar resultado si es necesario
        if not result.success and result.error_message:
            logger.debug("Ataque falló: %s", result.error_message)
            # El handler ya envió los mensajes necesarios, solo logueamos

    def _get_target_position(  # noqa: PLR6301
        self, x: int, y: int, heading: int
    ) -> tuple[int, int]:
        """Calcula la posición objetivo según la dirección del jugador.

        Args:
            x: Posición X del jugador.
            y: Posición Y del jugador.
            heading: Dirección del jugador (1=Norte, 2=Este, 3=Sur, 4=Oeste).

        Returns:
            Tupla (target_x, target_y).
        """
        # Constantes de dirección
        north, east, south = 1, 2, 3

        if heading == north:
            return x, y - 1
        if heading == east:
            return x + 1, y
        if heading == south:
            return x, y + 1
        # heading == 4:  # Oeste
        return x - 1, y
