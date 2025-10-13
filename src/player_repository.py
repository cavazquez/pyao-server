"""Repositorio para operaciones de jugadores usando Redis."""

import logging
from typing import TYPE_CHECKING

from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.redis_client import RedisClient

logger = logging.getLogger(__name__)


class PlayerRepository:
    """Repositorio para operaciones de datos de jugadores."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio.

        Args:
            redis_client: Cliente Redis para operaciones de bajo nivel.
        """
        self.redis = redis_client

    async def get_position(self, user_id: int) -> dict[str, int] | None:
        """Obtiene la posición del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con x, y, map o None si no existe.
        """
        key = RedisKeys.player_position(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "x": int(result.get("x", 50)),
            "y": int(result.get("y", 50)),
            "map": int(result.get("map", 1)),
        }

    async def set_position(self, user_id: int, x: int, y: int, map_number: int) -> None:
        """Guarda la posición del jugador.

        Args:
            user_id: ID del usuario.
            x: Posición X.
            y: Posición Y.
            map_number: Número del mapa.
        """
        key = RedisKeys.player_position(user_id)
        position_data = {
            "x": str(x),
            "y": str(y),
            "map": str(map_number),
        }
        await self.redis.redis.hset(key, mapping=position_data)  # type: ignore[misc]
        logger.debug(
            "Posición guardada para user_id %d: (%d, %d) en mapa %d", user_id, x, y, map_number
        )

    async def get_stats(self, user_id: int) -> dict[str, int] | None:
        """Obtiene las estadísticas del jugador (HP, mana, stamina, etc).

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con las estadísticas o None si no existe.
        """
        key = RedisKeys.player_user_stats(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "max_hp": int(result.get("max_hp", 100)),
            "min_hp": int(result.get("min_hp", 100)),
            "max_mana": int(result.get("max_mana", 100)),
            "min_mana": int(result.get("min_mana", 100)),
            "max_sta": int(result.get("max_sta", 100)),
            "min_sta": int(result.get("min_sta", 100)),
            "gold": int(result.get("gold", 0)),
            "level": int(result.get("level", 1)),
            "elu": int(result.get("elu", 300)),
            "experience": int(result.get("experience", 0)),
        }

    async def set_stats(  # noqa: PLR0913, PLR0917
        self,
        user_id: int,
        max_hp: int,
        min_hp: int,
        max_mana: int,
        min_mana: int,
        max_sta: int,
        min_sta: int,
        gold: int,
        level: int,
        elu: int,
        experience: int,
    ) -> None:
        """Guarda las estadísticas del jugador.

        Args:
            user_id: ID del usuario.
            max_hp: HP máximo.
            min_hp: HP actual.
            max_mana: Mana máximo.
            min_mana: Mana actual.
            max_sta: Stamina máxima.
            min_sta: Stamina actual.
            gold: Oro del jugador.
            level: Nivel del jugador.
            elu: Experiencia para subir de nivel.
            experience: Experiencia total.
        """
        key = RedisKeys.player_user_stats(user_id)
        stats_data = {
            "max_hp": str(max_hp),
            "min_hp": str(min_hp),
            "max_mana": str(max_mana),
            "min_mana": str(min_mana),
            "max_sta": str(max_sta),
            "min_sta": str(min_sta),
            "gold": str(gold),
            "level": str(level),
            "elu": str(elu),
            "experience": str(experience),
        }
        await self.redis.redis.hset(key, mapping=stats_data)  # type: ignore[misc]
        logger.debug("Estadísticas guardadas para user_id %d", user_id)

    async def get_hunger_thirst(self, user_id: int) -> dict[str, int] | None:
        """Obtiene hambre y sed del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con hambre y sed o None si no existe.
        """
        key = RedisKeys.player_hunger_thirst(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "max_water": int(result.get("max_water", 100)),
            "min_water": int(result.get("min_water", 100)),
            "max_hunger": int(result.get("max_hunger", 100)),
            "min_hunger": int(result.get("min_hunger", 100)),
        }

    async def set_hunger_thirst(
        self, user_id: int, max_water: int, min_water: int, max_hunger: int, min_hunger: int
    ) -> None:
        """Guarda hambre y sed del jugador.

        Args:
            user_id: ID del usuario.
            max_water: Sed máxima.
            min_water: Sed actual.
            max_hunger: Hambre máxima.
            min_hunger: Hambre actual.
        """
        key = RedisKeys.player_hunger_thirst(user_id)
        data = {
            "max_water": str(max_water),
            "min_water": str(min_water),
            "max_hunger": str(max_hunger),
            "min_hunger": str(min_hunger),
        }
        await self.redis.redis.hset(key, mapping=data)  # type: ignore[misc]
        logger.debug("Hambre y sed guardadas para user_id %d", user_id)

    async def get_attributes(self, user_id: int) -> dict[str, int] | None:
        """Obtiene los atributos del jugador (STR, AGI, INT, CHA, CON).

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con los atributos o None si no existe.
        """
        key = RedisKeys.player_stats(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "strength": int(result.get("strength", 10)),
            "agility": int(result.get("agility", 10)),
            "intelligence": int(result.get("intelligence", 10)),
            "charisma": int(result.get("charisma", 10)),
            "constitution": int(result.get("constitution", 10)),
        }

    async def set_attributes(  # noqa: PLR0913, PLR0917
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
        await self.redis.redis.hset(key, mapping=stats_data)  # type: ignore[misc]
        logger.debug("Atributos guardados para user_id %d", user_id)
