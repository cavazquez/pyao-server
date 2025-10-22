"""Tarea para manejar trabajo con click (pesca, tala, minería)."""

import logging
from typing import TYPE_CHECKING

from src.repositories.inventory_repository import InventoryRepository
from src.models.items_catalog import get_item
from src.task import Task

if TYPE_CHECKING:
    from src.repositories.inventory_repository import InventoryRepository
    from src.map_manager import MapManager
    from src.services.map.map_resources_service import MapResourcesService
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Tipos de habilidades de trabajo (enum Skill del cliente)
SKILL_TALAR = 9
SKILL_PESCA = 12
SKILL_MINERIA = 13


# IDs de herramientas
class ToolID:
    """IDs de herramientas de trabajo."""

    HACHA_LENADOR = 561
    PIQUETE_MINERO = 562
    CANA_PESCAR = 563


# IDs de recursos obtenidos
class ResourceItemID:
    """IDs de items que se obtienen al trabajar."""

    LENA = 58  # Leña
    MINERAL_HIERRO = 70  # Mineral de Hierro
    PESCADO = 68  # Pescado


class TaskWorkLeftClick(Task):
    """Maneja el trabajo con click (pesca, tala, minería) en coordenadas específicas."""

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
        """Inicializa la tarea de trabajo con click.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventarios.
            map_manager: Gestor de mapas.
            session_data: Datos de sesión.
            map_resources: Servicio de recursos del mapa.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.session_data = session_data
        self.map_resources = map_resources

    async def execute(self) -> None:
        """Ejecuta el trabajo en las coordenadas clickeadas."""
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

        # Parsear packet: PacketID (1 byte) + X (1 byte) + Y (1 byte) + Skill (1 byte)
        min_packet_size = 4
        if len(self.data) < min_packet_size:
            logger.warning("Packet WORK_LEFT_CLICK inválido: tamaño incorrecto")
            return

        target_x = self.data[1]
        target_y = self.data[2]
        skill_type = self.data[3]

        # Obtener mapa del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return

        map_id = position["map"]

        logger.info(
            "Usuario %d hace WORK_LEFT_CLICK en (%d, %d) con skill=%d",
            user_id,
            target_x,
            target_y,
            skill_type,
        )

        # Intentar trabajar en la posición clickeada
        work_result = await self._try_work_at_position(
            user_id, map_id, target_x, target_y, skill_type
        )

        if work_result:
            resource_name, item_id, quantity, slot = work_result
            await self.message_sender.console.send_console_msg(
                f"Has obtenido {quantity} {resource_name}"
            )
            await self._update_inventory_ui(user_id, item_id, slot)
            logger.info(
                "Usuario %d obtuvo %d %s (item_id=%d, slot=%d)",
                user_id,
                quantity,
                resource_name,
                item_id,
                slot,
            )
        else:
            await self.message_sender.console.send_console_msg(
                "No hay nada para trabajar en esa posición"
            )

    async def _update_inventory_ui(self, user_id: int, item_id: int, slot: int) -> None:
        """Actualiza la UI del inventario del cliente con el item obtenido."""
        if not self.inventory_repo:
            return

        item = get_item(item_id)
        if item:
            slot_data = await self.inventory_repo.get_slot(user_id, slot)
            if slot_data:
                total_quantity = slot_data[1]
                await self.message_sender.send_change_inventory_slot(
                    slot=slot,
                    item_id=item.item_id,
                    name=item.name,
                    amount=total_quantity,
                    equipped=False,
                    grh_id=item.graphic_id,
                    item_type=item.item_type.to_client_type(),
                    max_hit=item.max_damage or 0,
                    min_hit=item.min_damage or 0,
                    max_def=item.defense or 0,
                    min_def=item.defense or 0,
                    sale_price=float(item.value),
                )

    async def _try_work_at_position(
        self, user_id: int, map_id: int, target_x: int, target_y: int, skill_type: int
    ) -> tuple[str, int, int, int] | None:
        """Intenta trabajar en una posición específica.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa.
            target_x: Coordenada X del click.
            target_y: Coordenada Y del click.
            skill_type: Tipo de habilidad (9=Talar, 12=Pesca, 13=Minería).

        Returns:
            Tupla (nombre_recurso, item_id, cantidad, slot) si se pudo trabajar, None si no.
        """
        # Verificar herramienta en inventario
        if not self.inventory_repo or not self.map_resources:
            return None

        inventory = await self.inventory_repo.get_inventory_slots(user_id)

        has_hacha = any(slot.item_id == ToolID.HACHA_LENADOR for slot in inventory.values())
        has_pico = any(slot.item_id == ToolID.PIQUETE_MINERO for slot in inventory.values())
        has_cana = any(slot.item_id == ToolID.CANA_PESCAR for slot in inventory.values())

        # Verificar recursos según el tipo de skill
        if (
            skill_type == SKILL_TALAR
            and has_hacha
            and self.map_resources.has_tree(map_id, target_x, target_y)
        ):
            slots = await self.inventory_repo.add_item(
                user_id, item_id=ResourceItemID.LENA, quantity=5
            )
            if slots:
                return ("Leña", ResourceItemID.LENA, 5, slots[0][0])
            return None

        if (
            skill_type == SKILL_MINERIA
            and has_pico
            and self.map_resources.has_mine(map_id, target_x, target_y)
        ):
            slots = await self.inventory_repo.add_item(
                user_id, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
            )
            if slots:
                return ("Mineral de Hierro", ResourceItemID.MINERAL_HIERRO, 3, slots[0][0])
            return None

        if (
            skill_type == SKILL_PESCA
            and has_cana
            and self.map_resources.has_water(map_id, target_x, target_y)
        ):
            slots = await self.inventory_repo.add_item(
                user_id, item_id=ResourceItemID.PESCADO, quantity=2
            )
            if slots:
                return ("Pescado", ResourceItemID.PESCADO, 2, slots[0][0])
            return None

        # Si no tiene herramienta
        if not (has_hacha or has_pico or has_cana):
            await self.message_sender.console.send_console_msg(
                "Necesitas una herramienta (hacha, pico o caña de pescar)"
            )

        return None
