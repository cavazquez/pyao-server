"""Tarea para vender items a un mercader."""

import logging
import struct
from typing import TYPE_CHECKING

from src.items_catalog import ITEMS_CATALOG
from src.redis_config import RedisKeys
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.commerce_service import CommerceService
    from src.inventory_repository import InventoryRepository
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class TaskCommerceSell(Task):
    """Tarea que maneja la venta de items a un mercader."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        commerce_service: CommerceService | None = None,
        player_repo: PlayerRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de venta.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            commerce_service: Servicio de comercio.
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            redis_client: Cliente Redis.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.commerce_service = commerce_service
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.redis_client = redis_client
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa la venta de un item al mercader.

        El cliente envía: PacketID (1 byte) + Slot (1 byte) + Quantity (2 bytes)
        """
        # Leer parámetros del packet
        # Formato: PacketID (1 byte) + Slot (1 byte) + Quantity (2 bytes little-endian)
        slot = struct.unpack("B", self.data[1:2])[0]  # Slot del jugador (1-based)
        quantity = struct.unpack("<H", self.data[2:4])[0]  # Cantidad a vender (uint16 LE)

        logger.debug(
            "Cliente %s intenta vender: slot=%d, quantity=%d",
            self.message_sender.connection.address,
            slot,
            quantity,
        )

        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if not user_id:
            await self.message_sender.send_console_msg("Error: Sesión no válida")
            return

        # Validar servicios necesarios
        if not self.commerce_service or not self.player_repo or not self.inventory_repo:
            logger.error("TaskCommerceSell: Faltan servicios necesarios")
            return

        # Obtener NPC mercader activo de la sesión
        npc_id = await self._get_active_merchant(user_id)
        if not npc_id:
            await self.message_sender.send_console_msg("No tienes una ventana de comercio abierta")
            return

        # Ejecutar venta
        success, message = await self.commerce_service.sell_item(user_id, npc_id, slot, quantity)

        # Enviar mensaje de resultado
        await self.message_sender.send_console_msg(message)

        if success:
            # Actualizar oro del jugador
            await self._update_player_gold(user_id)

            # Actualizar inventario del jugador
            await self._update_player_inventory(user_id)

    async def _get_active_merchant(self, user_id: int) -> int | None:
        """Obtiene el ID del mercader activo para el jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            ID del mercader activo o None si no hay comercio activo.
        """
        if not self.redis_client:
            return None
        key = RedisKeys.session_active_merchant(user_id)
        result = await self.redis_client.redis.get(key)
        return int(result) if result else None

    async def _update_player_gold(self, user_id: int) -> None:
        """Envía actualización de oro al cliente.

        Args:
            user_id: ID del jugador.
        """
        if not self.player_repo:
            return
        gold = await self.player_repo.get_gold(user_id)
        await self.message_sender.send_update_gold(gold)

    async def _update_player_inventory(self, user_id: int) -> None:
        """Envía actualizaciones del inventario del jugador.

        Args:
            user_id: ID del jugador.
        """
        if not self.inventory_repo:
            return

        # Enviar todos los slots del inventario
        for slot in range(1, self.inventory_repo.MAX_SLOTS + 1):
            slot_data = await self.inventory_repo.get_slot(user_id, slot)

            if slot_data:
                item_id, amount = slot_data
                item = ITEMS_CATALOG.get(item_id)

                if item:
                    await self.message_sender.send_change_inventory_slot(
                        slot=slot,
                        item_id=item_id,
                        name=item.name,
                        amount=amount,
                        equipped=False,
                        grh_id=item.graphic_id,
                        item_type=item.item_type.to_client_type(),
                        max_hit=item.max_damage or 0,
                        min_hit=item.min_damage or 0,
                        max_def=item.defense or 0,
                        min_def=item.defense or 0,
                        sale_price=float(item.value),
                    )
            else:
                # Slot vacío
                await self.message_sender.send_change_inventory_slot(
                    slot=slot,
                    item_id=0,
                    name="",
                    amount=0,
                    equipped=False,
                    grh_id=0,
                    item_type=0,
                    max_hit=0,
                    min_hit=0,
                    max_def=0,
                    min_def=0,
                    sale_price=0.0,
                )
