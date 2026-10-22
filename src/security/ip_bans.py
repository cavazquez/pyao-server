"""Bloqueos IP autoritativos en Redis, sin depender de una caché de conexiones."""

import ipaddress
import json
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from redis.asyncio import Redis

IP_BANS_KEY = "security:ip_bans"


async def ip_is_blocked(redis: Redis, address: str) -> bool:
    """Consulta la dirección normalizada del peer, nunca una cabecera del cliente.

    Returns:
        Bloqueo activo de esta IP IPv4/IPv6.
    """
    ip = str(ipaddress.ip_address(address))
    encoded = await redis.hget(IP_BANS_KEY, ip)
    if not encoded:
        return False
    record = json.loads(encoded)
    return bool(
        record.get("active") and (not record.get("until") or float(record["until"]) > time.time())
    )
