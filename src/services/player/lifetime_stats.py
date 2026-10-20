"""Contadores persistentes: se incrementan en el mismo commit del daño letal."""

import math
import struct
import time
from typing import TYPE_CHECKING

from src.game.character_constants import JOB_ID_TO_CLASS_NAME
from src.network.packet_id import ServerPacketID
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository

DAY_SECONDS = 86400
MAX_COUNTER = 2**32 - 1


def increment(values: dict[str, str], field: str) -> str:
    """Incrementa sin desbordar el contador u32 del contrato.

    Returns:
        Nuevo valor decimal.
    """
    return str(min(MAX_COUNTER, int(values.get(field, 0)) + 1))


def kill_changes(source: dict[str, str], target: dict[str, str], *, player: bool) -> dict[str, str]:
    """Clasifica una baja confirmada, separada de las muertes propias.

    Returns:
        Campos del atacante; el caller valida la transición vivo a muerto.
    """
    if not player:
        return {"npc_kills": increment(source, "npc_kills")}
    kind = "criminal_kills" if target.get("criminal", "0") == "1" else "citizen_kills"
    return {"player_kills": increment(source, "player_kills"), kind: increment(source, kind)}


def remaining_days(stats: dict[str, str], *, now: float | None = None) -> int:
    """La condena transcurre también offline; se redondea hacia arriba.

    Returns:
        Días restantes, cero una vez vencida.
    """
    now = time.time() if now is None else now
    return max(0, math.ceil((float(stats.get("jail_until", 0)) - now) / DAY_SECONDS))


async def mini_stats_packet(
    player: PlayerRepository, account: AccountRepository, user: int
) -> bytes:
    """Lee los valores autoritativos sin modificar ni reinicializar contadores.

    Returns:
        MINI_STATS: cinco contadores u32, clase u8 y días restantes u32.
    """
    stats = await player.redis.hgetall(RedisKeys.player_user_stats(user))
    profile = await account.get_account_by_user_id(user) or {}
    job = int(profile.get("char_job", 1))
    if job not in JOB_ID_TO_CLASS_NAME:
        job = 1
    return struct.pack(
        "<BIIIIIBI",
        ServerPacketID.MINI_STATS,
        *(
            min(MAX_COUNTER, max(0, int(stats.get(field, 0))))
            for field in ("citizen_kills", "criminal_kills", "player_kills", "npc_kills", "deaths")
        ),
        job,
        min(MAX_COUNTER, remaining_days(stats)),
    )
