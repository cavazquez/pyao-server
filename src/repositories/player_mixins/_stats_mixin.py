"""Player repository mixins."""

import logging
from typing import TYPE_CHECKING

from src.models.player_stats import PlayerStats
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


logger = logging.getLogger(__name__)


class PlayerStatsMixin:
    """Core stats, hunger/thirst, and stat updaters."""

    async def get_stats(self, user_id: int) -> dict[str, int] | None:
        """Obtiene las estadísticas del jugador (HP, mana, stamina, etc).

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con las estadísticas o None si no existe.

        Note:
            Preferir get_player_stats() que retorna PlayerStats tipado.
        """
        stats = await self.get_player_stats(user_id)
        return stats.to_dict() if stats else None

    async def get_player_stats(self, user_id: int) -> PlayerStats | None:
        """Obtiene las estadísticas del jugador como objeto tipado.

        Args:
            user_id: ID del usuario.

        Returns:
            PlayerStats con las estadísticas o None si no existe.
        """
        key = RedisKeys.player_user_stats(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)

        if not result:
            return None

        return PlayerStats.from_dict(result)

    async def get_current_hp(self, user_id: int) -> int:
        """Obtiene el HP actual del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            HP actual (min_hp), 0 si el jugador no existe o está muerto.
        """
        stats = await self.get_player_stats(user_id)
        return stats.min_hp if stats else 0

    async def get_max_hp(self, user_id: int) -> int:
        """Obtiene el HP máximo del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            HP máximo, 100 por defecto si no existe.
        """
        stats = await self.get_player_stats(user_id)
        return stats.max_hp if stats else 100

    async def get_level(self, user_id: int) -> int:
        """Obtiene el nivel del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Nivel del jugador, 1 por defecto si no existe.
        """
        stats = await self.get_player_stats(user_id)
        return stats.level if stats else 1

    async def is_alive(self, user_id: int) -> bool:
        """Verifica si el jugador está vivo.

        Args:
            user_id: ID del usuario.

        Returns:
            True si el jugador existe y tiene HP > 0, False en caso contrario.
        """
        stats = await self.get_player_stats(user_id)
        return stats.is_alive if stats else False

    async def get_gold(self, user_id: int) -> int:
        """Obtiene el oro del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Oro del jugador, 0 por defecto si no existe.
        """
        stats = await self.get_player_stats(user_id)
        return stats.gold if stats else 0

    async def get_mana(self, user_id: int) -> tuple[int, int]:
        """Obtiene el mana actual y máximo del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla (min_mana, max_mana) con mana actual y máximo.
        """
        stats = await self.get_player_stats(user_id)
        if not stats:
            return (100, 100)
        return (stats.min_mana, stats.max_mana)

    async def get_experience(self, user_id: int) -> tuple[int, int]:
        """Obtiene experiencia y ELU del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla (experience, elu).
        """
        stats = await self.get_player_stats(user_id)
        if not stats:
            return (0, 300)
        return (stats.experience, stats.elu)

    async def set_stats(
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
        await self.redis.hset(key, mapping=stats_data)
        logger.debug("Estadísticas guardadas para user_id %d", user_id)

    async def get_hunger_thirst(self, user_id: int) -> dict[str, int] | None:
        """Obtiene hambre y sed del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con hambre, sed, flags y contadores o None si no existe.
        """
        key = RedisKeys.player_hunger_thirst(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)

        if not result:
            return None

        return {
            "max_water": int(result.get("max_water", 100)),
            "min_water": int(result.get("min_water", 100)),
            "max_hunger": int(result.get("max_hunger", 100)),
            "min_hunger": int(result.get("min_hunger", 100)),
            "thirst_flag": int(result.get("thirst_flag", 0)),
            "hunger_flag": int(result.get("hunger_flag", 0)),
            "water_counter": int(result.get("water_counter", 0)),
            "hunger_counter": int(result.get("hunger_counter", 0)),
        }

    async def set_hunger_thirst(
        self,
        user_id: int,
        max_water: int,
        min_water: int,
        max_hunger: int,
        min_hunger: int,
        thirst_flag: int = 0,
        hunger_flag: int = 0,
        water_counter: int = 0,
        hunger_counter: int = 0,
    ) -> None:
        """Guarda hambre y sed del jugador.

        Args:
            user_id: ID del usuario.
            max_water: Sed máxima.
            min_water: Sed actual.
            max_hunger: Hambre máxima.
            min_hunger: Hambre actual.
            thirst_flag: Flag de sed (1 si tiene sed, 0 si no).
            hunger_flag: Flag de hambre (1 si tiene hambre, 0 si no).
            water_counter: Contador para intervalo de sed.
            hunger_counter: Contador para intervalo de hambre.
        """
        key = RedisKeys.player_hunger_thirst(user_id)
        data = {
            "max_water": str(max_water),
            "min_water": str(min_water),
            "max_hunger": str(max_hunger),
            "min_hunger": str(min_hunger),
            "thirst_flag": str(thirst_flag),
            "hunger_flag": str(hunger_flag),
            "water_counter": str(water_counter),
            "hunger_counter": str(hunger_counter),
        }
        await self.redis.hset(key, mapping=data)
        logger.debug("Hambre y sed guardadas para user_id %d", user_id)

    async def set_meditating(self, user_id: int, is_meditating: bool) -> None:
        """Establece el estado de meditación del jugador."""
        key = RedisKeys.player_user_stats(user_id)
        await self._hset_field(key, "meditating", "1" if is_meditating else "0")
        logger.info("Meditación para user_id %d: %s", user_id, is_meditating)

    async def is_meditating(self, user_id: int) -> bool:
        """Verifica si el jugador está meditando.

        Returns:
            True si está meditando, False si no.
        """
        return await self._hget_bool(RedisKeys.player_user_stats(user_id), "meditating")

    async def set_sailing(self, user_id: int, is_sailing: bool) -> None:
        """Establece el estado de navegación (barca) del jugador."""
        key = RedisKeys.player_user_stats(user_id)
        await self._hset_field(key, "sailing", "1" if is_sailing else "0")
        logger.info("Navegación para user_id %d: %s", user_id, is_sailing)

    async def is_sailing(self, user_id: int) -> bool:
        """Verifica si el jugador está navegando en barca.

        Returns:
            True si está navegando, False si no.
        """
        return await self._hget_bool(RedisKeys.player_user_stats(user_id), "sailing")

    async def update_hp(self, user_id: int, hp: int) -> None:
        """Actualiza el HP del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "min_hp", hp)
        logger.debug("HP actualizado para user_id %d: %d", user_id, hp)

    async def update_experience(self, user_id: int, exp: int) -> None:
        """Actualiza la experiencia del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "experience", exp)
        logger.debug("Experiencia actualizada para user_id %d: %d", user_id, exp)

    async def update_level_and_elu(self, user_id: int, level: int, elu: int) -> None:
        """Actualiza el nivel y ELU del jugador.

        Args:
            user_id: ID del usuario.
            level: Nuevo nivel.
            elu: Nuevo ELU (experiencia para siguiente nivel).
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.hset(key, mapping={"level": str(level), "elu": str(elu)})
        logger.debug(
            "Nivel y ELU actualizados para user_id %d: nivel=%d, elu=%d", user_id, level, elu
        )

    async def update_gold(self, user_id: int, gold: int) -> None:
        """Actualiza el oro del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "gold", gold)
        logger.debug("Oro actualizado para user_id %d: %d", user_id, gold)

    async def add_gold(self, user_id: int, amount: int) -> int:
        """Agrega oro al jugador.

        Args:
            user_id: ID del usuario.
            amount: Cantidad de oro a agregar.

        Returns:
            Nueva cantidad total de oro.
        """
        current_gold = await self.get_gold(user_id)
        new_gold = current_gold + amount
        await self.update_gold(user_id, new_gold)
        logger.info("user_id %d recibió %d oro. Total: %d", user_id, amount, new_gold)
        return new_gold

    async def remove_gold(self, user_id: int, amount: int) -> bool:
        """Remueve oro del jugador.

        Args:
            user_id: ID del usuario.
            amount: Cantidad de oro a remover.

        Returns:
            True si se pudo remover, False si no tiene suficiente oro.
        """
        current_gold = await self.get_gold(user_id)
        if current_gold < amount:
            logger.debug(
                "user_id %d no tiene suficiente oro: tiene %d, intenta usar %d",
                user_id,
                current_gold,
                amount,
            )
            return False

        new_gold = current_gold - amount
        await self.update_gold(user_id, new_gold)
        logger.info("user_id %d gastó %d oro. Restante: %d", user_id, amount, new_gold)
        return True

    async def get_stamina(self, user_id: int) -> tuple[int, int]:
        """Obtiene la stamina actual y máxima del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Tupla (min_sta, max_sta) con stamina actual y máxima.
        """
        stats = await self.get_player_stats(user_id)
        if not stats:
            return (100, 100)
        return (stats.min_sta, stats.max_sta)

    async def update_mana(self, user_id: int, mana: int) -> None:
        """Actualiza el mana actual del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "min_mana", mana)
        logger.debug("Mana actualizado para user_id %d: %d", user_id, mana)

    async def update_stamina(self, user_id: int, stamina: int) -> None:
        """Actualiza la stamina actual del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "min_sta", stamina)
        logger.debug("Stamina actualizada para user_id %d: %d", user_id, stamina)
