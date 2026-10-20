"""Player repository mixins."""

import logging
from collections.abc import Sequence
from typing import TYPE_CHECKING

from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


logger = logging.getLogger(__name__)
POSITION_BATCH_SIZE = 256


def _position(result: dict[str, str]) -> dict[str, int]:
    """Decodifica una posición existente conservando los defaults del repositorio.

    Returns:
        Posición y orientación del jugador.
    """
    return {
        "x": int(result.get("x", 50)),
        "y": int(result.get("y", 50)),
        "map": int(result.get("map", 1)),
        "heading": int(result.get("heading", 3)),
    }


class PlayerPositionMixin:
    """Position and heading operations."""

    async def get_position(self, user_id: int) -> dict[str, int] | None:
        """Obtiene la posición del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con x, y, map, heading o None si no existe.
        """
        key = RedisKeys.player_position(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)

        if not result:
            return None

        return _position(result)

    async def get_positions(
        self, user_ids: Sequence[int], *, alive_only: bool = False
    ) -> dict[int, dict[str, int]]:
        """Lee candidatos en lotes acotados, sin conservar snapshots entre acciones.

        El filtro de vida sólo lee HP. No consulta ni liquida saldos de oro para
        elegir un objetivo; el ataque vuelve a validar su estado autoritativo.

        Args:
            user_ids: Jugadores solicitados, en orden de selección.
            alive_only: Excluye jugadores sin estadísticas o con HP <= 0.

        Returns:
            Posiciones existentes, por ID, con los defaults de get_position.
        """
        ids = list(dict.fromkeys(user_ids))
        positions: dict[int, dict[str, int]] = {}
        for start in range(0, len(ids), POSITION_BATCH_SIZE):
            batch = ids[start : start + POSITION_BATCH_SIZE]
            async with self.redis.redis.pipeline(transaction=False) as pipe:
                for user_id in batch:
                    pipe.hgetall(RedisKeys.player_position(user_id))
                    if alive_only:
                        pipe.hgetall(RedisKeys.player_user_stats(user_id))
                rows = await pipe.execute()
            stride = 2 if alive_only else 1
            for index, user_id in enumerate(batch):
                row = rows[index * stride]
                if not row:
                    continue
                if alive_only:
                    stats = rows[index * stride + 1]
                    if not stats or int(stats.get("min_hp", stats.get("hp", 100))) <= 0:
                        continue
                positions[user_id] = _position(row)
        return positions

    async def set_position(
        self, user_id: int, x: int, y: int, map_number: int, heading: int | None = None
    ) -> None:
        """Guarda la posición del jugador.

        Args:
            user_id: ID del usuario.
            x: Posición X.
            y: Posición Y.
            map_number: Número del mapa.
            heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste), opcional.
        """
        key = RedisKeys.player_position(user_id)
        position_data = {
            "x": str(x),
            "y": str(y),
            "map": str(map_number),
        }
        if heading is not None:
            position_data["heading"] = str(heading)
        await self.redis.hset(key, mapping=position_data)
        logger.debug(
            "Posición guardada para user_id %d: (%d, %d) en mapa %d", user_id, x, y, map_number
        )

    async def set_heading(self, user_id: int, heading: int) -> None:
        """Actualiza solo la dirección del jugador.

        Args:
            user_id: ID del usuario.
            heading: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste).
        """
        key = RedisKeys.player_position(user_id)
        await self.redis.hset(key, "heading", str(heading))
        logger.debug("Dirección actualizada para user_id %d: heading=%d", user_id, heading)
