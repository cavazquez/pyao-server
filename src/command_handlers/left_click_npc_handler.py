"""Handler especializado para clicks en NPCs."""

import logging
from typing import TYPE_CHECKING, Any

from src.models.items_catalog import ITEMS_CATALOG
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.bank_repository import BankRepository
    from src.repositories.merchant_repository import MerchantRepository
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class LeftClickNPCHandler:
    """Handler especializado para clicks en NPCs."""

    def __init__(
        self,
        merchant_repo: MerchantRepository | None,
        bank_repo: BankRepository | None,
        redis_client: RedisClient | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de clicks en NPCs.

        Args:
            merchant_repo: Repositorio de mercaderes.
            bank_repo: Repositorio de banco.
            redis_client: Cliente Redis.
            message_sender: Enviador de mensajes.
        """
        self.merchant_repo = merchant_repo
        self.bank_repo = bank_repo
        self.redis_client = redis_client
        self.message_sender = message_sender

    async def handle_npc_click(
        self, user_id: int, npc: NPC
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Maneja click en un NPC.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC.

        Returns:
            Tupla (success, error_message, data).
        """
        # Si es un mercader, abrir ventana de comercio
        if npc.is_merchant:
            return await self._handle_merchant_click(user_id, npc)

        # Si es un banquero, abrir ventana de banco
        if npc.is_banker:
            return await self._handle_banker_click(user_id, npc)

        # Mostrar información básica del NPC
        return await self._handle_npc_info_click(user_id, npc)

    async def _handle_merchant_click(
        self, user_id: int, npc: NPC
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Maneja click en un mercader.

        Returns:
            Tupla (success, error_message, data).
        """
        if not self.merchant_repo or not self.redis_client:
            logger.error("Dependencias no disponibles para abrir comercio")
            await self.message_sender.send_console_msg("Error al abrir comercio")
            return False, "Error al abrir comercio", None

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
            return True, None, {"merchant_id": npc.npc_id, "items_count": 0, "type": "merchant"}

        # Preparar lista de items para el packet COMMERCE_INIT
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
                    item.value,
                    item.graphic_id,
                    item.item_type.to_client_type(),
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

        return (
            True,
            None,
            {"merchant_id": npc.npc_id, "items_count": len(items_data), "type": "merchant"},
        )

    async def _handle_banker_click(
        self, user_id: int, npc: NPC
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Maneja click en un banquero.

        Returns:
            Tupla (success, error_message, data).
        """
        if not self.bank_repo:
            logger.error("BankRepository no disponible")
            await self.message_sender.send_console_msg("El banco no está disponible")
            return False, "El banco no está disponible", None

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

        # Enviar oro del banco
        bank_gold = await self.bank_repo.get_gold(user_id)
        await self.message_sender.send_update_bank_gold(bank_gold)

        logger.info(
            "Ventana de banco abierta para user_id %d con banquero %s (%d items, %d oro)",
            user_id,
            npc.name,
            len(bank_items),
            bank_gold,
        )

        return (
            True,
            None,
            {
                "banker_id": npc.npc_id,
                "items_count": len(bank_items),
                "gold": bank_gold,
                "type": "bank",
            },
        )

    async def _handle_npc_info_click(
        self, user_id: int, npc: NPC
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Maneja click en un NPC para mostrar información.

        Returns:
            Tupla (success, error_message, data).
        """
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

        return True, None, {"npc_name": npc.name, "npc_id": npc.npc_id, "type": "info"}
