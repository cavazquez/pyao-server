"""Player repository mixins."""

import logging
from typing import TYPE_CHECKING

from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


logger = logging.getLogger(__name__)


class PlayerStatusMixin:
    """Status effects and combat state flags."""

    async def _get_status_timestamp(self, user_id: int, effect: str) -> float:
        """Obtiene el timestamp de un efecto de estado genérico.

        Args:
            user_id: ID del usuario.
            effect: Nombre del efecto (ej: "poisoned", "immobilized", "blinded").

        Returns:
            Timestamp hasta cuando está activo (0.0 = inactivo).
        """
        return await self._hget_float(RedisKeys.player_user_stats(user_id), f"{effect}_until")

    async def _set_status_timestamp(self, user_id: int, effect: str, timestamp: float) -> None:
        """Establece el timestamp de un efecto de estado genérico.

        Args:
            user_id: ID del usuario.
            effect: Nombre del efecto (ej: "poisoned", "immobilized").
            timestamp: Timestamp hasta cuando está activo (0.0 = desactivar).
        """
        await self._hset_field(RedisKeys.player_user_stats(user_id), f"{effect}_until", timestamp)
        logger.debug("Effect '%s' updated for user_id %d: until %.2f", effect, user_id, timestamp)

    async def get_poisoned_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está envenenado.

        Returns:
            Timestamp hasta cuando está envenenado (0.0 = no envenenado).
        """
        return await self._get_status_timestamp(user_id, "poisoned")

    async def update_poisoned_until(self, user_id: int, poisoned_until: float) -> None:
        """Actualiza el estado de envenenamiento del jugador."""
        await self._set_status_timestamp(user_id, "poisoned", poisoned_until)
        logger.debug("Envenenamiento user_id %d: hasta %.2f", user_id, poisoned_until)

    async def get_immobilized_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está inmovilizado.

        Returns:
            Timestamp hasta cuando está inmovilizado (0.0 = no inmovilizado).
        """
        return await self._get_status_timestamp(user_id, "immobilized")

    async def update_immobilized_until(self, user_id: int, immobilized_until: float) -> None:
        """Actualiza el estado de inmovilización del jugador."""
        await self._set_status_timestamp(user_id, "immobilized", immobilized_until)
        logger.debug("Inmovilización user_id %d: hasta %.2f", user_id, immobilized_until)

    async def get_blinded_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está ciego.

        Returns:
            Timestamp hasta cuando está ciego (0.0 = no ciego).
        """
        return await self._get_status_timestamp(user_id, "blinded")

    async def update_blinded_until(self, user_id: int, blinded_until: float) -> None:
        """Actualiza el estado de ceguera del jugador."""
        await self._set_status_timestamp(user_id, "blinded", blinded_until)
        logger.debug("Ceguera actualizada para user_id %d: hasta %.2f", user_id, blinded_until)

    async def get_dumb_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está estúpido.

        Returns:
            Timestamp hasta cuando está estúpido (0.0 = no estúpido).
        """
        return await self._get_status_timestamp(user_id, "dumb")

    async def update_dumb_until(self, user_id: int, dumb_until: float) -> None:
        """Actualiza el estado de stupidez del jugador."""
        await self._set_status_timestamp(user_id, "dumb", dumb_until)
        logger.debug("Estupidez actualizada para user_id %d: hasta %.2f", user_id, dumb_until)

    async def get_morphed_appearance(self, user_id: int) -> dict[str, int | float] | None:
        """Obtiene la apariencia morfeada del jugador.

        Returns:
            Diccionario con morphed_body, morphed_head, morphed_until o None si no está morfeado.
        """
        key = RedisKeys.player_user_stats(user_id)
        result = await self.redis.hmget(key, ["morphed_body", "morphed_head", "morphed_until"])
        if not result or not result[0] or not result[1] or not result[2]:
            return None
        try:
            return {
                "morphed_body": int(result[0]),
                "morphed_head": int(result[1]),
                "morphed_until": float(result[2]),
            }
        except ValueError, TypeError:
            return None

    async def set_morphed_appearance(
        self, user_id: int, morphed_body: int, morphed_head: int, morphed_until: float
    ) -> None:
        """Establece la apariencia morfeada del jugador.

        Args:
            user_id: ID del usuario.
            morphed_body: Body ID del target.
            morphed_head: Head ID del target.
            morphed_until: Timestamp hasta cuando está morfeado (0.0 = no morfeado).
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.hset(
            key,
            mapping={
                "morphed_body": str(morphed_body),
                "morphed_head": str(morphed_head),
                "morphed_until": str(morphed_until),
            },
        )
        logger.debug(
            "Apariencia morfeada establecida para user_id %d: body=%d head=%d hasta %.2f",
            user_id,
            morphed_body,
            morphed_head,
            morphed_until,
        )

    async def clear_morphed_appearance(self, user_id: int) -> None:
        """Elimina la apariencia morfeada del jugador.

        Args:
            user_id: ID del usuario.
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.hdel(key, "morphed_body", "morphed_head", "morphed_until")
        logger.debug("Apariencia morfeada eliminada para user_id %d", user_id)

    async def get_invisible_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está invisible.

        Returns:
            Timestamp hasta cuando está invisible (0.0 = no invisible).
        """
        return await self._get_status_timestamp(user_id, "invisible")

    async def update_invisible_until(self, user_id: int, invisible_until: float) -> None:
        """Actualiza el estado de invisibilidad del jugador."""
        await self._set_status_timestamp(user_id, "invisible", invisible_until)
        logger.debug("Invisibilidad user_id %d: hasta %.2f", user_id, invisible_until)

    async def get_safe_mode(self, user_id: int) -> bool:
        """Obtiene el estado del modo seguro (anti-PvP) del jugador.

        Returns:
            True si el modo seguro está activo, False en caso contrario.
        """
        return await self._hget_bool(RedisKeys.player_user_stats(user_id), "safe_mode")

    async def set_safe_mode(self, user_id: int, safe_mode: bool) -> None:
        """Establece el modo seguro (anti-PvP) del jugador.

        Args:
            user_id: ID del usuario.
            safe_mode: True para activar, False para desactivar.
        """
        await self._hset_field(
            RedisKeys.player_user_stats(user_id), "safe_mode", 1 if safe_mode else 0
        )
        logger.info("Safe mode toggled for user_id %d: %s", user_id, "ON" if safe_mode else "OFF")
