"""Handler especializado para validaciones de trabajo con click."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class WorkLeftClickValidationHandler:
    """Handler especializado para validaciones de trabajo con click."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de validaciones.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.message_sender = message_sender

    async def check_distance(self, user_id: int, target_x: int, target_y: int) -> bool:
        """Verifica que el target esté a distancia 1 del jugador.

        Args:
            user_id: ID del usuario.
            target_x: Coordenada X objetivo.
            target_y: Coordenada Y objetivo.

        Returns:
            True si está a distancia válida, False si no.
        """
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return False

        player_x = position["x"]
        player_y = position["y"]

        if max(abs(target_x - player_x), abs(target_y - player_y)) > 1:
            await self.message_sender.console.send_console_msg(
                "Debes estar a un tile de distancia para trabajar."
            )
            logger.info(
                "Usuario %d intentó trabajar demasiado lejos: player=(%d,%d), target=(%d,%d)",
                user_id,
                player_x,
                player_y,
                target_x,
                target_y,
            )
            return False

        return True

    async def check_tools(
        self, user_id: int
    ) -> tuple[bool, bool, bool]:  # (has_hacha, has_pico, has_cana)
        """Verifica qué herramientas tiene el jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla (has_hacha, has_pico, has_cana).
        """
        from src.constants.items import ToolID  # noqa: PLC0415

        inventory = await self.inventory_repo.get_inventory_slots(user_id)

        has_hacha = any(slot.item_id == ToolID.HACHA_LENADOR for slot in inventory.values())
        has_pico = any(slot.item_id == ToolID.PIQUETE_MINERO for slot in inventory.values())
        has_cana = any(slot.item_id == ToolID.CANA_PESCAR for slot in inventory.values())

        return (has_hacha, has_pico, has_cana)

    async def check_no_tools(self, has_hacha: bool, has_pico: bool, has_cana: bool) -> bool:
        """Verifica si el jugador no tiene herramientas y envía mensaje.

        Args:
            has_hacha: Si tiene hacha.
            has_pico: Si tiene pico.
            has_cana: Si tiene caña.

        Returns:
            True si no tiene herramientas, False si tiene al menos una.
        """
        if not (has_hacha or has_pico or has_cana):
            await self.message_sender.console.send_console_msg(
                "Necesitas una herramienta (hacha, pico o caña de pescar)"
            )
            return True
        return False
