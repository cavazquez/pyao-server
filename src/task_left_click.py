"""Tarea para click izquierdo en personajes/NPCs."""

import logging
import struct
from typing import TYPE_CHECKING

from src.items_catalog import ITEMS_CATALOG
from src.redis_config import RedisKeys
from src.session_manager import SessionManager
from src.task import Task

if TYPE_CHECKING:
    from src.bank_repository import BankRepository
    from src.map_manager import MapManager
    from src.merchant_repository import MerchantRepository
    from src.message_sender import MessageSender
    from src.npc import NPC
    from src.player_repository import PlayerRepository
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class TaskLeftClick(Task):
    """Maneja click izquierdo en personajes/NPCs."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        merchant_repo: MerchantRepository | None = None,
        bank_repo: BankRepository | None = None,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de click izquierdo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            merchant_repo: Repositorio de mercaderes.
            bank_repo: Repositorio de banco.
            redis_client: Cliente Redis.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.merchant_repo = merchant_repo
        self.bank_repo = bank_repo
        self.redis_client = redis_client
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta click izquierdo en personaje/NPC."""
        # Parsear el packet: PacketID (1 byte) + X (1 byte) + Y (1 byte)
        min_packet_size = 3
        if len(self.data) < min_packet_size:
            logger.warning("Packet LEFT_CLICK inválido: tamaño incorrecto")
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de click sin estar logueado")
            return

        if not self.map_manager or not self.player_repo:
            logger.error("Dependencias no disponibles para click en NPC")
            return

        try:
            # Extraer coordenadas X, Y (1 byte cada una)
            x = struct.unpack("B", self.data[1:2])[0]
            y = struct.unpack("B", self.data[2:3])[0]

            logger.info("user_id %d hizo click en posición (%d, %d)", user_id, x, y)

            # Obtener posición del jugador para saber en qué mapa está
            position = await self.player_repo.get_position(user_id)
            if not position:
                logger.warning("No se pudo obtener posición del jugador %d", user_id)
                return

            map_id = position["map"]

            # Buscar NPC en esa posición
            all_npcs = self.map_manager.get_npcs_in_map(map_id)
            npc_found = None
            for npc in all_npcs:
                if npc.x == x and npc.y == y:
                    npc_found = npc
                    break

            if npc_found:
                await self._handle_npc_click(user_id, npc_found)
            else:
                # No hay NPC en esa posición, podría ser otro jugador
                logger.debug("No se encontró NPC en posición (%d, %d) del mapa %d", x, y, map_id)
                await self.message_sender.send_console_msg(f"No hay nadie en ({x}, {y}).")

        except struct.error:
            logger.exception("Error al parsear packet LEFT_CLICK")

    async def _handle_npc_click(self, user_id: int, npc: NPC) -> None:
        """Maneja click en un NPC.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC.
        """
        # Si es un mercader, abrir ventana de comercio
        if npc.is_merchant:
            await self._open_merchant_window(user_id, npc)
            return

        # Si es un banquero, abrir ventana de banco
        if npc.is_banker:
            await self._open_bank_window(user_id, npc)
            return

        # Mostrar información básica del NPC (solo ASCII para evitar crashes)
        info_parts = [f"[{npc.name}]"]

        if npc.description:
            info_parts.append(npc.description)

        if npc.is_hostile:
            info_parts.append(f"Nivel {npc.level} - Hostil")
        else:
            info_parts.append(f"Nivel {npc.level} - Amigable")

        info_parts.append(f"HP: {npc.hp}/{npc.max_hp}")

        info_message = " | ".join(info_parts)
        await self.message_sender.send_console_msg(info_message)

        logger.info(
            "user_id %d obtuvo información de NPC %s (CharIndex: %d)",
            user_id,
            npc.name,
            npc.char_index,
        )

    async def _open_merchant_window(self, user_id: int, npc: NPC) -> None:
        """Abre la ventana de comercio con un mercader.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC mercader.
        """
        if not self.merchant_repo or not self.redis_client:
            logger.error("Dependencias no disponibles para abrir comercio")
            await self.message_sender.send_console_msg("Error al abrir comercio")
            return

        logger.info(
            "user_id %d abriendo comercio con %s (npc_id=%d)", user_id, npc.name, npc.npc_id
        )

        # Guardar mercader activo en sesión de Redis
        key = RedisKeys.session_active_merchant(user_id)
        await self.redis_client.redis.set(key, str(npc.npc_id))

        # Enviar packet COMMERCE_INIT vacío PRIMERO (abre la ventana)
        await self.message_sender.send_commerce_init_empty()

        # Obtener inventario del mercader
        merchant_items = await self.merchant_repo.get_all_items(npc.npc_id)

        if not merchant_items:
            await self.message_sender.send_console_msg(f"{npc.name} no tiene nada para vender.")
            logger.warning("Mercader %d no tiene inventario", npc.npc_id)
            return

        # Preparar lista de items para el packet COMMERCE_INIT
        # Formato: (slot, item_id, name, quantity, price, grh_index, obj_type,
        #           max_hit, min_hit, max_def, min_def)
        items_data = []
        for merchant_item in merchant_items:
            item = ITEMS_CATALOG.get(merchant_item.item_id)
            if not item:
                logger.warning("Item %d no encontrado en catálogo", merchant_item.item_id)
                continue

            items_data.append(
                (
                    merchant_item.slot,
                    merchant_item.item_id,
                    item.name,
                    merchant_item.quantity,
                    item.value,  # Precio de compra
                    item.graphic_id,
                    item.item_type.to_client_type(),  # Convertir enum a número del protocolo
                    item.max_damage or 0,
                    item.min_damage or 0,
                    item.defense or 0,
                    item.defense or 0,
                )
            )

        # Enviar items del mercader usando ChangeNPCInventorySlot
        for item_data in items_data:
            (
                slot,
                item_id,
                name,
                quantity,
                price,
                grh_index,
                obj_type,
                max_hit,
                min_hit,
                max_def,
                min_def,
            ) = item_data
            await self.message_sender.send_change_npc_inventory_slot(
                slot=slot,
                name=name,
                amount=quantity,
                sale_price=float(price),
                grh_id=grh_index,
                item_id=item_id,
                item_type=obj_type,
                max_hit=max_hit,
                min_hit=min_hit,
                max_def=max_def,
                min_def=min_def,
            )

        logger.info(
            "Ventana de comercio abierta para user_id %d con mercader %s (%d items)",
            user_id,
            npc.name,
            len(items_data),
        )

    async def _open_bank_window(self, user_id: int, npc: NPC) -> None:
        """Abre la ventana de banco para el jugador.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC banquero.
        """
        if not self.bank_repo:
            logger.error("BankRepository no disponible")
            await self.message_sender.send_console_msg("El banco no está disponible")
            return

        logger.info("user_id %d abriendo banco con %s (npc_id=%d)", user_id, npc.name, npc.npc_id)

        # Enviar packet BANK_INIT vacío PRIMERO (abre la ventana)
        await self.message_sender.send_bank_init_empty()

        # Obtener todos los items del banco
        bank_items = await self.bank_repo.get_all_items(user_id)

        # Enviar items del banco usando ChangeBankSlot
        for bank_item in bank_items:
            item = ITEMS_CATALOG.get(bank_item.item_id)
            if not item:
                logger.warning("Item %d no encontrado en catálogo", bank_item.item_id)
                continue

            await self.message_sender.send_change_bank_slot(
                slot=bank_item.slot,
                item_id=bank_item.item_id,
                name=item.name,
                amount=bank_item.quantity,
                grh_id=item.graphic_id,
                item_type=item.item_type.to_client_type(),
                max_hit=item.max_damage or 0,
                min_hit=item.min_damage or 0,
                max_def=item.defense or 0,
                min_def=item.defense or 0,
            )

        logger.info(
            "Ventana de banco abierta para user_id %d con banquero %s (%d items)",
            user_id,
            npc.name,
            len(bank_items),
        )
