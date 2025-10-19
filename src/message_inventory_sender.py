"""Componente para enviar información de inventario, banco y comercio al cliente."""

import logging
from typing import TYPE_CHECKING

from src.msg import build_change_inventory_slot_response, build_commerce_init_response
from src.packet_builder import PacketBuilder
from src.packet_id import ServerPacketID

if TYPE_CHECKING:
    from src.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class InventoryMessageSender:
    """Maneja el envío de información de inventario, banco y comercio al cliente."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de inventario.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection

    async def send_change_inventory_slot(
        self,
        slot: int,
        item_id: int,
        name: str,
        amount: int,
        equipped: bool,
        grh_id: int,
        item_type: int,
        max_hit: int = 0,
        min_hit: int = 0,
        max_def: int = 0,
        min_def: int = 0,
        sale_price: float = 0.0,
    ) -> None:
        """Envía actualización de un slot del inventario.

        Args:
            slot: Número de slot (1-20).
            item_id: ID del item.
            name: Nombre del item.
            amount: Cantidad.
            equipped: Si está equipado.
            grh_id: ID del gráfico.
            item_type: Tipo de item.
            max_hit: Daño máximo.
            min_hit: Daño mínimo.
            max_def: Defensa máxima.
            min_def: Defensa mínima.
            sale_price: Precio de venta.
        """
        response = build_change_inventory_slot_response(
            slot=slot,
            item_id=item_id,
            name=name,
            amount=amount,
            equipped=equipped,
            grh_id=grh_id,
            item_type=item_type,
            max_hit=max_hit,
            min_hit=min_hit,
            max_def=max_def,
            min_def=min_def,
            sale_price=sale_price,
        )
        logger.debug(
            "[%s] Enviando CHANGE_INVENTORY_SLOT: slot=%d, item=%s, amount=%d",
            self.connection.address,
            slot,
            name,
            amount,
        )
        await self.connection.send(response)

    async def send_change_bank_slot(
        self,
        slot: int,
        item_id: int,
        name: str,
        amount: int,
        grh_id: int,
        item_type: int,
        max_hit: int,
        min_hit: int,
        max_def: int,
        min_def: int,
    ) -> None:
        """Envía paquete ChangeBankSlot para actualizar un slot de la bóveda bancaria.

        Args:
            slot: Número de slot (1-20).
            item_id: ID del item.
            name: Nombre del item.
            amount: Cantidad.
            grh_id: ID gráfico.
            item_type: Tipo de item.
            max_hit: Daño máximo.
            min_hit: Daño mínimo.
            max_def: Defensa máxima.
            min_def: Defensa mínima.
        """
        packet = PacketBuilder()
        packet.add_byte(ServerPacketID.CHANGE_BANK_SLOT)
        packet.add_byte(slot)
        packet.add_int16(item_id)
        packet.add_unicode_string(name)
        packet.add_int16(amount)
        packet.add_int16(grh_id)
        packet.add_byte(item_type)
        packet.add_int16(max_hit)
        packet.add_int16(min_hit)
        packet.add_int16(max_def)
        packet.add_int16(min_def)

        await self.connection.send(packet.to_bytes())

    async def send_change_npc_inventory_slot(
        self,
        slot: int,
        name: str,
        amount: int,
        sale_price: float,
        grh_id: int,
        item_id: int,
        item_type: int,
        max_hit: int,
        min_hit: int,
        max_def: int,
        min_def: int,
    ) -> None:
        """Envía paquete ChangeNPCInventorySlot para actualizar un slot del inventario del mercader.

        Args:
            slot: Número de slot (1-20).
            name: Nombre del item.
            amount: Cantidad.
            sale_price: Precio de venta (float).
            grh_id: ID gráfico.
            item_id: ID del item.
            item_type: Tipo de item.
            max_hit: Daño máximo.
            min_hit: Daño mínimo.
            max_def: Defensa máxima.
            min_def: Defensa mínima.
        """
        packet = PacketBuilder()
        packet.add_byte(ServerPacketID.CHANGE_NPC_INVENTORY_SLOT)
        packet.add_byte(slot)
        packet.add_unicode_string(name)
        packet.add_int16(amount)
        packet.add_float(sale_price)
        packet.add_int16(grh_id)
        packet.add_int16(item_id)
        packet.add_byte(item_type)
        packet.add_int16(max_hit)
        packet.add_int16(min_hit)
        packet.add_int16(max_def)
        packet.add_int16(min_def)

        await self.connection.send(packet.to_bytes())

    async def send_bank_init_empty(self) -> None:
        """Envía paquete BANK_INIT vacío (solo abre la ventana)."""
        response = bytes([ServerPacketID.BANK_INIT])
        logger.debug("[%s] Enviando BANK_INIT (vacío)", self.connection.address)
        await self.connection.send(response)

    async def send_bank_end(self) -> None:
        """Envía packet BANK_END para cerrar la ventana de banco."""
        response = bytes([ServerPacketID.BANK_END])
        logger.info("[%s] Enviando BANK_END", self.connection.address)
        await self.connection.send(response)

    async def send_commerce_init_empty(self) -> None:
        """Envía paquete COMMERCE_INIT vacío (solo abre la ventana)."""
        response = bytes([ServerPacketID.COMMERCE_INIT])
        logger.debug("[%s] Enviando COMMERCE_INIT (vacío)", self.connection.address)
        await self.connection.send(response)

    async def send_commerce_init(
        self,
        npc_id: int,
        items: list[tuple[int, int, str, int, int, int, int, int, int, int, int]],
    ) -> None:
        """Envía paquete COMMERCE_INIT para abrir ventana de comercio con inventario del mercader.

        Args:
            npc_id: ID del NPC mercader.
            items: Lista de tuplas con formato:
                (slot, item_id, name, quantity, price, grh_index, obj_type,
                 max_hit, min_hit, max_def, min_def)
        """
        response = build_commerce_init_response(npc_id=npc_id, items=items)
        logger.debug(
            "[%s] Enviando COMMERCE_INIT: npc_id=%d, num_items=%d",
            self.connection.address,
            npc_id,
            len(items),
        )
        await self.connection.send(response)

    async def send_commerce_end(self) -> None:
        """Envía paquete CommerceEnd para cerrar la ventana de comercio."""
        response = bytes([ServerPacketID.COMMERCE_END])
        logger.debug("[%s] Enviando COMMERCE_END", self.connection.address)
        await self.connection.send(response)

    async def send_change_spell_slot(self, slot: int, spell_id: int, spell_name: str) -> None:
        """Envía actualización de un slot de hechizo.

        Args:
            slot: Número de slot (1-based).
            spell_id: ID del hechizo.
            spell_name: Nombre del hechizo.
        """
        packet = PacketBuilder()
        packet.add_byte(ServerPacketID.CHANGE_SPELL_SLOT)
        packet.add_byte(slot)
        packet.add_int16(spell_id)
        packet.add_unicode_string(spell_name)
        response = packet.to_bytes()

        logger.debug(
            "[%s] Enviando CHANGE_SPELL_SLOT: slot=%d, spell_id=%d, name=%s",
            self.connection.address,
            slot,
            spell_id,
            spell_name,
        )
        await self.connection.send(response)

    async def send_meditate_toggle(self) -> None:
        """Envía paquete MEDITATE_TOGGLE para confirmar meditación."""
        response = bytes([ServerPacketID.MEDITATE_TOGGLE])
        logger.debug("[%s] Enviando MEDITATE_TOGGLE", self.connection.address)
        await self.connection.send(response)
