"""Player repository mixins."""

import logging
import time
from typing import TYPE_CHECKING

from src.models.player_stats import PlayerAttributes
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


logger = logging.getLogger(__name__)


class PlayerAttributesMixin:
    """Base attributes and temporary modifiers."""

    async def get_attributes(self, user_id: int) -> dict[str, int] | None:
        """Obtiene atributos del jugador con modificadores temporales aplicados.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con los atributos o None si no existe.

        Note:
            Preferir get_player_attributes() que retorna PlayerAttributes tipado.
        """
        attrs = await self.get_player_attributes(user_id)
        return attrs.to_dict() if attrs else None

    async def get_player_attributes(self, user_id: int) -> PlayerAttributes | None:
        """Obtiene atributos del jugador como objeto tipado.

        Args:
            user_id: ID del usuario.

        Returns:
            PlayerAttributes con los atributos o None si no existe.
        """
        key = RedisKeys.player_stats(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)

        if not result:
            return None

        # Atributos base (sin modificadores)
        base_strength_value = int(result.get("strength", 10))
        base_agility_value = int(result.get("agility", 10))

        # Aplicar modificadores temporales si están activos
        current_time = time.time()

        # Modificador de fuerza
        strength_until, strength_modifier = await self.get_strength_modifier(user_id)
        final_strength = base_strength_value
        if strength_until > current_time and strength_modifier != 0:
            final_strength = base_strength_value + strength_modifier
            # Limitar al doble del valor base o máximo permitido (como en VB6)
            max_strength = min(50, base_strength_value * 2)
            min_strength = 1
            final_strength = max(min_strength, min(final_strength, max_strength))

        # Modificador de agilidad
        agility_until, agility_modifier = await self.get_agility_modifier(user_id)
        final_agility = base_agility_value
        if agility_until > current_time and agility_modifier != 0:
            final_agility = base_agility_value + agility_modifier
            # Limitar al doble del valor base o máximo permitido (como en VB6)
            max_agility = min(50, base_agility_value * 2)
            min_agility = 1
            final_agility = max(min_agility, min(final_agility, max_agility))

        return PlayerAttributes(
            strength=final_strength,
            agility=final_agility,
            intelligence=int(result.get("intelligence", 10)),
            charisma=int(result.get("charisma", 10)),
            constitution=int(result.get("constitution", 10)),
        )

    async def get_strength(self, user_id: int) -> int:
        """Obtiene la fuerza del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Fuerza del jugador, 10 por defecto si no existe.
        """
        attributes = await self.get_player_attributes(user_id)
        return attributes.strength if attributes else 10

    async def get_agility(self, user_id: int) -> int:
        """Obtiene la agilidad del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Agilidad del jugador, 10 por defecto si no existe.
        """
        attributes = await self.get_player_attributes(user_id)
        return attributes.agility if attributes else 10

    async def get_intelligence(self, user_id: int) -> int:
        """Obtiene la inteligencia del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Inteligencia del jugador, 10 por defecto si no existe.
        """
        attributes = await self.get_player_attributes(user_id)
        return attributes.intelligence if attributes else 10

    async def get_charisma(self, user_id: int) -> int:
        """Obtiene el carisma del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Carisma del jugador, 10 por defecto si no existe.
        """
        attributes = await self.get_player_attributes(user_id)
        return attributes.charisma if attributes else 10

    async def get_constitution(self, user_id: int) -> int:
        """Obtiene la constitución del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Constitución del jugador, 10 por defecto si no existe.
        """
        attributes = await self.get_player_attributes(user_id)
        return attributes.constitution if attributes else 10

    async def set_attributes(
        self,
        user_id: int,
        strength: int,
        agility: int,
        intelligence: int,
        charisma: int,
        constitution: int,
    ) -> None:
        """Guarda los atributos del jugador.

        Args:
            user_id: ID del usuario.
            strength: Fuerza.
            agility: Agilidad.
            intelligence: Inteligencia.
            charisma: Carisma.
            constitution: Constitución.
        """
        key = RedisKeys.player_stats(user_id)
        stats_data = {
            "strength": str(strength),
            "agility": str(agility),
            "intelligence": str(intelligence),
            "charisma": str(charisma),
            "constitution": str(constitution),
        }
        await self.redis.hset(key, mapping=stats_data)
        logger.debug("Atributos guardados para user_id %d", user_id)

    async def _get_modifier(self, user_id: int, name: str) -> tuple[float, int]:
        """Obtiene un modificador temporal de atributo.

        Args:
            user_id: ID del usuario.
            name: Nombre del atributo (strength, agility).

        Returns:
            Tupla (expires_at, modifier_value). Si no hay modificador, retorna (0.0, 0).
        """
        key = RedisKeys.player_stats(user_id)
        until = await self._hget_float(key, f"{name}_modifier_until")
        value = await self._hget_int(key, f"{name}_modifier_value")
        return (until, value)

    async def _set_modifier(
        self, user_id: int, name: str, expires_at: float, modifier_value: int
    ) -> None:
        """Establece un modificador temporal de atributo."""
        key = RedisKeys.player_stats(user_id)
        await self.redis.hset(
            key,
            mapping={
                f"{name}_modifier_until": str(expires_at),
                f"{name}_modifier_value": str(modifier_value),
            },
        )
        logger.debug(
            "Modificador de %s para user_id %d: valor=%d, expira=%.2f",
            name,
            user_id,
            modifier_value,
            expires_at,
        )

    async def get_strength_modifier(self, user_id: int) -> tuple[float, int]:
        """Obtiene el modificador temporal de fuerza.

        Returns:
            Tupla (expires_at, modifier_value).
        """
        return await self._get_modifier(user_id, "strength")

    async def set_strength_modifier(
        self, user_id: int, expires_at: float, modifier_value: int
    ) -> None:
        """Establece el modificador temporal de fuerza."""
        await self._set_modifier(user_id, "strength", expires_at, modifier_value)

    async def get_agility_modifier(self, user_id: int) -> tuple[float, int]:
        """Obtiene el modificador temporal de agilidad.

        Returns:
            Tupla (expires_at, modifier_value).
        """
        return await self._get_modifier(user_id, "agility")

    async def set_agility_modifier(
        self, user_id: int, expires_at: float, modifier_value: int
    ) -> None:
        """Establece el modificador temporal de agilidad."""
        await self._set_modifier(user_id, "agility", expires_at, modifier_value)
