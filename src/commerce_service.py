"""Servicio de comercio con NPCs mercaderes."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.inventory_repository import InventoryRepository
    from src.item import Item
    from src.merchant_repository import MerchantRepository
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class CommerceService:
    """Gestiona transacciones de compra/venta con mercaderes."""

    def __init__(
        self,
        inventory_repo: "InventoryRepository",  # noqa: UP037
        merchant_repo: "MerchantRepository",  # noqa: UP037
        item_catalog: "dict[int, Item]",  # noqa: UP037
        player_repo: "PlayerRepository",  # noqa: UP037
    ) -> None:
        """Inicializa el servicio de comercio.

        Args:
            inventory_repo: Repositorio de inventarios de jugadores.
            merchant_repo: Repositorio de inventarios de mercaderes.
            item_catalog: Catálogo de items del juego.
            player_repo: Repositorio de datos de jugadores.
        """
        self.inventory_repo = inventory_repo
        self.merchant_repo = merchant_repo
        self.player_repo = player_repo
        self.items_catalog = item_catalog

    async def buy_item(
        self,
        user_id: int,
        npc_id: int,
        slot: int,
        quantity: int,
    ) -> tuple[bool, str]:
        """Comprar item de un mercader.

        Args:
            user_id: ID del jugador.
            npc_id: ID del NPC mercader.
            slot: Slot del inventario del mercader (1-based).
            quantity: Cantidad a comprar.

        Returns:
            Tupla (éxito, mensaje).
        """
        # Validar cantidad
        if quantity <= 0:
            return False, "Cantidad inválida"

        # Obtener item del mercader
        merchant_item = await self.merchant_repo.get_item(npc_id, slot)
        if not merchant_item:
            return False, "El mercader no tiene ese item"

        if merchant_item.quantity < quantity:
            return False, f"El mercader solo tiene {merchant_item.quantity} disponibles"

        # Obtener datos del item del catálogo
        item = self.items_catalog.get(merchant_item.item_id)
        if not item:
            logger.error("Item %d no encontrado en catálogo", merchant_item.item_id)
            return False, "Item no encontrado"

        # Verificar que el item tenga precio
        if item.value <= 0:
            logger.warning(
                "Intento de comprar item %d (%s) sin precio del mercader %d",
                item.item_id,
                item.name,
                npc_id,
            )
            return False, "Este item no está a la venta"

        # Calcular precio total
        total_price = item.value * quantity

        # Verificar oro del jugador
        player_gold = await self.player_repo.get_gold(user_id)
        if player_gold < total_price:
            return False, f"No tienes suficiente oro. Necesitas {total_price} oro."

        # Verificar espacio en inventario
        # TODO: Implementar has_space_for_item que considere stackable items
        has_space = await self.inventory_repo.has_space(user_id)
        if not has_space:
            return False, "Tu inventario está lleno"

        # Realizar transacción
        try:
            # Restar oro
            new_gold = player_gold - total_price
            await self.player_repo.update_gold(user_id, new_gold)

            # Agregar item al inventario del jugador
            modified_slots = await self.inventory_repo.add_item(
                user_id, merchant_item.item_id, quantity
            )

            if not modified_slots:
                # Rollback: devolver oro
                await self.player_repo.update_gold(user_id, player_gold)
                logger.error(
                    "No se pudo agregar item %d al inventario de user_id %d",
                    merchant_item.item_id,
                    user_id,
                )
                return False, "No se pudo agregar el item al inventario"

            # Restar item del inventario del mercader
            success = await self.merchant_repo.remove_item(npc_id, slot, quantity)
            if not success:
                # Rollback: devolver oro y remover items
                await self.player_repo.update_gold(user_id, player_gold)
                for mod_slot, _ in modified_slots:
                    await self.inventory_repo.remove_item(user_id, mod_slot, quantity)
                logger.error(
                    "No se pudo remover item del mercader %d, slot %d",
                    npc_id,
                    slot,
                )
                return False, "Error al procesar la compra"

            logger.info(
                "user_id %d compró %dx %s (item_id=%d) por %d oro del mercader %d",
                user_id,
                quantity,
                item.name,
                item.item_id,
                total_price,
                npc_id,
            )

        except Exception:
            logger.exception("Error en transacción de compra")
            return False, "Error al procesar la compra"

        return True, f"Has comprado {quantity}x {item.name} por {total_price} oro"

    async def sell_item(
        self,
        user_id: int,
        npc_id: int,
        slot: int,
        quantity: int,
    ) -> tuple[bool, str]:
        """Vender item a un mercader.

        Args:
            user_id: ID del jugador.
            npc_id: ID del NPC mercader.
            slot: Slot del inventario del jugador (1-based).
            quantity: Cantidad a vender.

        Returns:
            Tupla (éxito, mensaje).
        """
        # Validar cantidad
        if quantity <= 0:
            return False, "Cantidad inválida"

        # Obtener item del jugador
        player_item = await self.inventory_repo.get_slot(user_id, slot)
        if not player_item:
            return False, "No tienes ese item"

        item_id, current_quantity = player_item
        if current_quantity < quantity:
            return False, f"Solo tienes {current_quantity} disponibles"

        # Obtener datos del item del catálogo
        item = self.items_catalog.get(item_id)
        if not item:
            logger.error("Item %d no encontrado en catálogo", item_id)
            return False, "Item no encontrado"

        # Verificar si el item se puede vender
        if item.value == 0:
            return False, "Este item no se puede vender"

        # Calcular precio de venta (50% del precio de compra)
        sale_price = item.value // 2
        total_price = sale_price * quantity

        # Realizar transacción
        try:
            # Remover item del inventario del jugador
            success = await self.inventory_repo.remove_item(user_id, slot, quantity)
            if not success:
                logger.error(
                    "No se pudo remover item del inventario de user_id %d, slot %d",
                    user_id,
                    slot,
                )
                return False, "No se pudo remover el item"

            # Sumar oro al jugador
            player_gold = await self.player_repo.get_gold(user_id)
            new_gold = player_gold + total_price
            await self.player_repo.update_gold(user_id, new_gold)

            # Agregar item al inventario del mercader
            merchant_success = await self.merchant_repo.add_item(npc_id, item_id, quantity)
            if not merchant_success:
                logger.warning(
                    "Inventario del mercader %d lleno, item %d no agregado",
                    npc_id,
                    item_id,
                )
                # No hacemos rollback porque el mercader puede tener inventario lleno
                # El jugador ya vendió el item y recibió el oro

            logger.info(
                "user_id %d vendió %dx %s (item_id=%d) por %d oro al mercader %d",
                user_id,
                quantity,
                item.name,
                item_id,
                total_price,
                npc_id,
            )

        except Exception:
            logger.exception("Error en transacción de venta")
            return False, "Error al procesar la venta"

        return True, f"Has vendido {quantity}x {item.name} por {total_price} oro"
