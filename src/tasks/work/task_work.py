"""Tarea que maneja el trabajo de los jugadores (talar, minar, pescar)."""

import logging
from typing import TYPE_CHECKING

from src.constants.items import ResourceItemID, ToolID
from src.repositories.inventory_repository import InventoryRepository
from src.game.map_manager import MapManager
from src.messaging.message_sender import MessageSender
from src.repositories.player_repository import PlayerRepository
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.repositories.inventory_repository import InventoryRepository
    from src.game.map_manager import MapManager
    from src.services.map.map_resources_service import MapResourcesService
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constantes de direcciones (headings)
HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4


class TaskWork(Task):
    """Tarea que maneja el trabajo de los jugadores."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        map_manager: MapManager | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        map_resources: MapResourcesService | None = None,
    ) -> None:
        """Inicializa la tarea de trabajo.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventarios.
            map_manager: Gestor de mapas.
            session_data: Datos de sesión compartidos.
            map_resources: Servicio de recursos del mapa.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.session_data = session_data
        self.map_resources = map_resources

    async def execute(self) -> None:
        """Ejecuta la lógica de trabajo."""
        # Validar dependencias
        if not self.player_repo or not self.inventory_repo or not self.map_manager:
            logger.error("Repositorios no disponibles para trabajar")
            await self.message_sender.console.send_error_msg("Servicio de trabajo no disponible")
            return

        if not self.session_data or "user_id" not in self.session_data:
            logger.warning("No hay sesión activa para trabajar")
            await self.message_sender.console.send_error_msg("Debes iniciar sesión primero")
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Obtener posición y dirección del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return

        x = position["x"]
        y = position["y"]
        map_id = position["map"]
        heading = position["heading"]

        # Calcular posición objetivo (enfrente del jugador)
        target_x, target_y = TaskWork._get_target_position(x, y, heading)

        logger.info(
            "Usuario %d intenta trabajar en (%d, %d) mirando dirección %d -> objetivo (%d, %d)",
            user_id,
            x,
            y,
            heading,
            target_x,
            target_y,
        )

        # Verificar si hay un recurso trabajable en la posición objetivo
        work_result = await self._try_work_at_position(user_id, map_id, target_x, target_y)

        if work_result:
            resource_name, item_id, quantity = work_result
            await self.message_sender.console.send_console_msg(
                f"Has obtenido {quantity} {resource_name}"
            )
            logger.info(
                "Usuario %d obtuvo %d %s (item_id=%d)",
                user_id,
                quantity,
                resource_name,
                item_id,
            )
        else:
            await self.message_sender.console.send_console_msg(
                "No hay nada para trabajar en esa dirección"
            )

    @staticmethod
    def _get_target_position(x: int, y: int, heading: int) -> tuple[int, int]:
        """Calcula la posición objetivo basándose en la dirección del jugador.

        Args:
            x: Posición X del jugador.
            y: Posición Y del jugador.
            heading: Dirección del jugador (1=Norte, 2=Este, 3=Sur, 4=Oeste).

        Returns:
            Tupla (target_x, target_y) de la posición objetivo.
        """
        if heading == HEADING_NORTH:
            return (x, y - 1)
        if heading == HEADING_EAST:
            return (x + 1, y)
        if heading == HEADING_SOUTH:
            return (x, y + 1)
        if heading == HEADING_WEST:
            return (x - 1, y)
        return (x, y)  # Fallback

    async def _try_work_at_position(
        self, user_id: int, map_id: int, target_x: int, target_y: int
    ) -> tuple[str, int, int] | None:
        """Intenta trabajar en una posición específica.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa.
            target_x: Coordenada X objetivo.
            target_y: Coordenada Y objetivo.

        Returns:
            Tupla (nombre_recurso, item_id, cantidad) si se pudo trabajar, None si no.
        """
        # Verificar herramienta equipada o en inventario
        if not self.inventory_repo:
            return None

        inventory = await self.inventory_repo.get_inventory_slots(user_id)

        has_hacha = any(slot.item_id == ToolID.HACHA_LENADOR for slot in inventory.values())
        has_pico = any(slot.item_id == ToolID.PIQUETE_MINERO for slot in inventory.values())
        has_cana = any(slot.item_id == ToolID.CANA_PESCAR for slot in inventory.values())

        # Verificar recursos usando MapResourcesService
        if self.map_resources:
            if has_hacha and self.map_resources.has_tree(map_id, target_x, target_y):
                await self.inventory_repo.add_item(user_id, item_id=ResourceItemID.LENA, quantity=5)
                return ("Leña", ResourceItemID.LENA, 5)

            if has_pico and self.map_resources.has_mine(map_id, target_x, target_y):
                await self.inventory_repo.add_item(
                    user_id, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
                )
                return ("Mineral de Hierro", ResourceItemID.MINERAL_HIERRO, 3)

            if has_cana and self.map_resources.has_water(map_id, target_x, target_y):
                await self.inventory_repo.add_item(
                    user_id, item_id=ResourceItemID.PESCADO, quantity=2
                )
                return ("Pescado", ResourceItemID.PESCADO, 2)

        # Si no tiene herramienta
        if not (has_hacha or has_pico or has_cana):
            await self.message_sender.console.send_console_msg(
                "Necesitas una herramienta (hacha, pico o caña de pescar)"
            )

        return None
