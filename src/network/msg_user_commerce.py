"""Constructores de paquetes para comercio entre jugadores."""

from src.network.packet_builder import PacketBuilder
from src.network.packet_id import ServerPacketID


def build_user_commerce_init_response(partner_username: str) -> bytes:
    """Construye packet USER_COMMERCE_INIT con el nombre del otro jugador.

    Returns:
        Bytes listos para enviar al cliente.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.USER_COMMERCE_INIT)
    packet.add_unicode_string(partner_username)
    return packet.to_bytes()


def build_user_commerce_end_response() -> bytes:
    """Construye packet USER_COMMERCE_END sin payload.

    Returns:
        Bytes listos para enviar al cliente.
    """
    packet = PacketBuilder()
    packet.add_byte(ServerPacketID.USER_COMMERCE_END)
    return packet.to_bytes()
