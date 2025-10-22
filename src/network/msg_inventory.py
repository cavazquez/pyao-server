"""Construcción de mensajes de inventario, banco y comercio."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_change_inventory_slot_response(
    slot: int,
    item_id: int,
    name: str,
    amount: int,
    equipped: bool,
    grh_id: int,
    item_type: int,
    max_hit: int,
    min_hit: int,
    max_def: int,
    min_def: int,
    sale_price: float,
) -> bytes:
    """Construye el paquete para actualizar un slot del inventario.

    Args:
        slot: Número de slot (1-20).
        item_id: ID del item (index).
        name: Nombre del item.
        amount: Cantidad del item.
        equipped: Si está equipado (True/False).
        grh_id: ID del gráfico.
        item_type: Tipo de item.
        max_hit: Daño máximo.
        min_hit: Daño mínimo.
        max_def: Defensa máxima.
        min_def: Defensa mínima.
        sale_price: Precio de venta.

    Returns:
        Paquete de bytes con el formato del cliente.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHANGE_INVENTORY_SLOT)
    packet.add_byte(slot)
    packet.add_int16(item_id)
    packet.add_unicode_string(name)
    packet.add_int16(amount)
    packet.add_byte(1 if equipped else 0)
    packet.add_int16(grh_id)
    packet.add_byte(item_type)
    # Cliente espera: maxHit, minHit, maxDef, minDef
    packet.add_int16(max_hit)
    packet.add_int16(min_hit)
    packet.add_int16(max_def)
    packet.add_int16(min_def)
    packet.add_float(sale_price)
    return packet.to_bytes()


def build_change_bank_slot_response(
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
) -> bytes:
    """Construye el paquete ChangeBankSlot del protocolo AO estándar.

    Args:
        slot: Número de slot (byte).
        item_id: ID del item (int16).
        name: Nombre del item (string).
        amount: Cantidad (int16).
        grh_id: ID gráfico (int16).
        item_type: Tipo de item (byte).
        max_hit: Daño máximo (int16).
        min_hit: Daño mínimo (int16).
        max_def: Defensa máxima (int16).
        min_def: Defensa mínima (int16).

    Returns:
        Paquete de bytes con el formato ChangeBankSlot.
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
    return packet.to_bytes()


def build_change_npc_inventory_slot_response(
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
) -> bytes:
    """Construye el paquete ChangeNPCInventorySlot del protocolo AO estándar.

    Args:
        slot: Número de slot (byte).
        name: Nombre del item (string).
        amount: Cantidad (int16).
        sale_price: Precio de venta (float).
        grh_id: ID gráfico (int16).
        item_id: ID del item (int16).
        item_type: Tipo de item (byte).
        max_hit: Daño máximo (int16).
        min_hit: Daño mínimo (int16).
        max_def: Defensa máxima (int16).
        min_def: Defensa mínima (int16).

    Returns:
        Paquete de bytes con el formato ChangeNPCInventorySlot.
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
    return packet.to_bytes()


def build_change_spell_slot_response(slot: int, spell_id: int, spell_name: str) -> bytes:
    """Construye el paquete ChangeSpellSlot del protocolo AO estándar.

    Args:
        slot: Número de slot (byte).
        spell_id: ID del hechizo (int16).
        spell_name: Nombre del hechizo (string).

    Returns:
        Paquete de bytes con el formato ChangeSpellSlot.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.CHANGE_SPELL_SLOT)
    packet.add_byte(slot)
    packet.add_int16(spell_id)
    packet.add_unicode_string(spell_name)
    return packet.to_bytes()


def build_commerce_end_response() -> bytes:
    """Construye el paquete CommerceEnd del protocolo AO estándar.

    Returns:
        Paquete de bytes con el formato del cliente.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.COMMERCE_END)
    return packet.to_bytes()


def build_commerce_init_response(
    npc_id: int,
    items: list[tuple[int, int, str, int, int, int, int, int, int, int, int]],
) -> bytes:
    """Construye el paquete COMMERCE_INIT del protocolo AO estándar.

    Args:
        npc_id: ID del NPC mercader.
        items: Lista de tuplas con formato:
            (slot, item_id, name, quantity, price, grh_index, obj_type,
             max_hit, min_hit, max_def, min_def)

    Returns:
        Paquete de bytes con el formato del cliente.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.COMMERCE_INIT)
    packet.add_int16(npc_id)
    packet.add_byte(len(items))

    for (
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
    ) in items:
        packet.add_byte(slot)
        packet.add_int16(item_id)
        packet.add_unicode_string(name)
        packet.add_int16(quantity)
        packet.add_int16(price)  # Cambiado de int32 a int16
        packet.add_int16(grh_index)
        packet.add_byte(obj_type)
        packet.add_int16(max_hit)
        packet.add_int16(min_hit)
        packet.add_int16(max_def)
        packet.add_int16(min_def)

    return packet.to_bytes()
