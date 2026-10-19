"""Canales explícitos para clientes nuevos y consola sin cambios para clientes legacy."""

from typing import TYPE_CHECKING

from src.network.capabilities import Capability
from src.network.state_channel import send_state

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.network.client_connection import ClientConnection
    from src.network.state_channel import StateSender

CHAT_CHANNELS = frozenset({"system", "public", "whisper", "party", "clan"})
MAX_CHAT_CHUNK = 480


def supports_chat(connection: ClientConnection | None) -> bool:
    """Comprueba la negociación sin interpretar fuentes ni colores.

    Returns:
        Si existe una conexión autenticada que solicitó el contrato estructurado.
    """
    enabled = getattr(getattr(connection, "capabilities", None), "enabled", 0)
    return (
        connection is not None
        and connection.is_authenticated is True
        and isinstance(enabled, int)
        and bool(enabled & Capability.WORLD_STATE)
    )


async def emit_chat(
    sender: StateSender,
    channel: str,
    user_id: int,
    username: str,
    message: str,
    *,
    context: str = "",
    font: int = 7,
    recipient: int = 0,
    recipient_name: str = "",
) -> None:
    """Divide texto sin pérdida; los campos de identidad los calcula el servidor.

    Raises:
        ValueError: Si una llamada interna intenta usar un canal desconocido.
    """
    if channel not in CHAT_CHANNELS:
        error = "Canal de chat desconocido"
        raise ValueError(error)
    for offset in range(0, max(1, len(message)), MAX_CHAT_CHUNK):
        await send_state(
            sender,
            "chat",
            {
                "channel": channel,
                "sender_id": user_id,
                "sender": username[:20],
                "text": message[offset : offset + MAX_CHAT_CHUNK],
                "context": context[:32],
                "font": font,
                "recipient": recipient,
                "recipient_name": recipient_name[:20],
            },
        )


async def deliver_chat(
    sender: MessageSender,
    channel: str,
    user_id: int,
    username: str,
    message: str,
    *,
    legacy: str,
    context: str = "",
    font: int = 7,
    recipient: int = 0,
    recipient_name: str = "",
) -> None:
    """Elige una sola representación por conexión y preserva el texto legacy."""
    if supports_chat(getattr(sender, "connection", None)):
        await emit_chat(
            sender,
            channel,
            user_id,
            username,
            message,
            context=context,
            font=font,
            recipient=recipient,
            recipient_name=recipient_name,
        )
    else:
        await sender.send_console_msg(legacy, font_color=font)
