"""Repositorio para operaciones de jugadores usando Redis."""

import logging
import time
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.models.player_stats import PlayerAttributes, PlayerStats
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object

logger = logging.getLogger(__name__)


class PlayerRepository:
    """Repositorio para operaciones de datos de jugadores."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio.

        Args:
            redis_client: Cliente Redis para operaciones de bajo nivel.
        """
        self.redis = redis_client

    # ── Redis hash helpers ──────────────────────────────────────────────

    async def _hget_float(self, key: str, field: str, default: float = 0.0) -> float:
        """Lee un campo float de un hash Redis.

        Returns:
            Valor float del campo o default si no existe / es inválido.
        """
        result = await self.redis.redis.hget(key, field)  # type: ignore[misc]
        if not result:
            return default
        try:
            return float(result)
        except ValueError, TypeError:
            return default

    async def _hget_int(self, key: str, field: str, default: int = 0) -> int:
        """Lee un campo int de un hash Redis.

        Returns:
            Valor int del campo o default si no existe / es inválido.
        """
        result = await self.redis.redis.hget(key, field)  # type: ignore[misc]
        if not result:
            return default
        try:
            return int(result)
        except ValueError, TypeError:
            return default

    async def _hget_bool(self, key: str, field: str) -> bool:
        """Lee un campo booleano (1/0) de un hash Redis.

        Returns:
            True si el campo es "1", False en caso contrario.
        """
        result = await self.redis.redis.hget(key, field)  # type: ignore[misc]
        return result in {b"1", "1", 1} if result else False

    async def _hset_field(self, key: str, field: str, value: str | float) -> None:
        """Escribe un campo en un hash Redis."""
        await self.redis.redis.hset(key, field, str(value))  # type: ignore[misc]

    # ── Position ────────────────────────────────────────────────────────

    async def get_position(self, user_id: int) -> dict[str, int] | None:
        """Obtiene la posición del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con x, y, map, heading o None si no existe.
        """
        key = RedisKeys.player_position(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "x": int(result.get("x", 50)),
            "y": int(result.get("y", 50)),
            "map": int(result.get("map", 1)),
            "heading": int(result.get("heading", 3)),  # 3 = Sur por defecto
        }

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
        await self.redis.redis.hset(key, mapping=position_data)  # type: ignore[misc]
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
        await self.redis.redis.hset(key, "heading", str(heading))  # type: ignore[misc]
        logger.debug("Dirección actualizada para user_id %d: heading=%d", user_id, heading)

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
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

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
        await self.redis.redis.hset(key, mapping=stats_data)  # type: ignore[misc]
        logger.debug("Estadísticas guardadas para user_id %d", user_id)

    async def get_hunger_thirst(self, user_id: int) -> dict[str, int] | None:
        """Obtiene hambre y sed del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con hambre, sed, flags y contadores o None si no existe.
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
        await self.redis.redis.hset(key, mapping=data)  # type: ignore[misc]
        logger.debug("Hambre y sed guardadas para user_id %d", user_id)

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
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

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
        await self.redis.redis.hset(key, mapping=stats_data)  # type: ignore[misc]
        logger.debug("Atributos guardados para user_id %d", user_id)

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

    # ── Status effects (timestamps) ────────────────────────────────────

    async def get_poisoned_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está envenenado.

        Returns:
            Timestamp hasta cuando está envenenado (0.0 = no envenenado).
        """
        return await self._hget_float(RedisKeys.player_user_stats(user_id), "poisoned_until")

    async def update_poisoned_until(self, user_id: int, poisoned_until: float) -> None:
        """Actualiza el estado de envenenamiento del jugador."""
        key = RedisKeys.player_user_stats(user_id)
        await self._hset_field(key, "poisoned_until", poisoned_until)
        logger.debug("Envenenamiento user_id %d: hasta %.2f", user_id, poisoned_until)

    async def get_immobilized_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está inmovilizado.

        Returns:
            Timestamp hasta cuando está inmovilizado (0.0 = no inmovilizado).
        """
        return await self._hget_float(RedisKeys.player_user_stats(user_id), "immobilized_until")

    async def update_immobilized_until(self, user_id: int, immobilized_until: float) -> None:
        """Actualiza el estado de inmovilización del jugador."""
        await self._hset_field(
            RedisKeys.player_user_stats(user_id), "immobilized_until", immobilized_until
        )
        logger.debug("Inmovilización user_id %d: hasta %.2f", user_id, immobilized_until)

    async def get_blinded_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está ciego.

        Returns:
            Timestamp hasta cuando está ciego (0.0 = no ciego).
        """
        return await self._hget_float(RedisKeys.player_user_stats(user_id), "blinded_until")

    async def update_blinded_until(self, user_id: int, blinded_until: float) -> None:
        """Actualiza el estado de ceguera del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "blinded_until", blinded_until)
        logger.debug("Ceguera actualizada para user_id %d: hasta %.2f", user_id, blinded_until)

    async def get_dumb_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está estúpido.

        Returns:
            Timestamp hasta cuando está estúpido (0.0 = no estúpido).
        """
        return await self._hget_float(RedisKeys.player_user_stats(user_id), "dumb_until")

    async def update_dumb_until(self, user_id: int, dumb_until: float) -> None:
        """Actualiza el estado de estupidez del jugador."""
        await self._hset_field(RedisKeys.player_user_stats(user_id), "dumb_until", dumb_until)
        logger.debug("Estupidez actualizada para user_id %d: hasta %.2f", user_id, dumb_until)

    async def get_morphed_appearance(self, user_id: int) -> dict[str, int | float] | None:
        """Obtiene la apariencia morfeada del jugador.

        Returns:
            Diccionario con morphed_body, morphed_head, morphed_until o None si no está morfeado.
        """
        key = RedisKeys.player_user_stats(user_id)
        result = await self.redis.redis.hmget(  # type: ignore[misc]
            key, ["morphed_body", "morphed_head", "morphed_until"]
        )
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
        await self.redis.redis.hset(  # type: ignore[misc]
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
        await self.redis.redis.hdel(  # type: ignore[misc]
            key, "morphed_body", "morphed_head", "morphed_until"
        )
        logger.debug("Apariencia morfeada eliminada para user_id %d", user_id)

    async def get_invisible_until(self, user_id: int) -> float:
        """Obtiene el timestamp hasta cuando el jugador está invisible.

        Returns:
            Timestamp hasta cuando está invisible (0.0 = no invisible).
        """
        return await self._hget_float(RedisKeys.player_user_stats(user_id), "invisible_until")

    async def update_invisible_until(self, user_id: int, invisible_until: float) -> None:
        """Actualiza el estado de invisibilidad del jugador."""
        await self._hset_field(
            RedisKeys.player_user_stats(user_id), "invisible_until", invisible_until
        )
        logger.debug("Invisibilidad user_id %d: hasta %.2f", user_id, invisible_until)

    # ── Attribute modifiers (buffs/debuffs) ────────────────────────────

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
        await self.redis.redis.hset(  # type: ignore[misc]
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

    # ── Single-field updaters ──────────────────────────────────────────

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
        await self.redis.redis.hset(  # type: ignore[misc]
            key, mapping={"level": str(level), "elu": str(elu)}
        )
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

    async def get_skills(self, user_id: int) -> dict[str, int] | None:
        """Obtiene las habilidades del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con las habilidades o None si no existe.
        """
        key = RedisKeys.player_skills(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "magia": int(result.get("magia", 0)),
            "robustez": int(result.get("robustez", 0)),
            "agilidad": int(result.get("agilidad", 0)),
            "talar": int(result.get("talar", 0)),
            "pesca": int(result.get("pesca", 0)),
            "mineria": int(result.get("mineria", 0)),
            "herreria": int(result.get("herreria", 0)),
            "carpinteria": int(result.get("carpinteria", 0)),
            "supervivencia": int(result.get("supervivencia", 0)),
            "liderazgo": int(result.get("liderazgo", 0)),
        }

    async def set_skills(self, user_id: int, **skills: int) -> None:
        """Guarda las habilidades del jugador.

        Args:
            user_id: ID del usuario.
            **skills: Habilidades a guardar (magia, robustez, etc.).
        """
        key = RedisKeys.player_skills(user_id)
        if skills:
            await self.redis.redis.hset(key, mapping={k: str(v) for k, v in skills.items()})  # type: ignore[misc]
            logger.debug(
                "Habilidades actualizadas para user_id %d: %s", user_id, list(skills.keys())
            )

    async def add_skill_experience(
        self, user_id: int, skill_name: str, exp_gained: int
    ) -> tuple[int, bool]:
        """Añade experiencia a una habilidad específica y retorna nueva experiencia.

        y si subió de nivel.

        Args:
            user_id: ID del usuario.
            skill_name: Nombre de la habilidad (ej: 'talar', 'pesca', 'mineria').
            exp_gained: Experiencia a añadir.

        Returns:
            Tupla (nueva_experiencia, subio_de_nivel).
        """
        # Obtener experiencia actual
        skills = await self.get_skills(user_id) or {}
        current_exp = skills.get(skill_name, 0)
        new_exp = current_exp + exp_gained

        # Calcular nivel (configurable)
        exp_per_level = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
        old_level = current_exp // exp_per_level
        new_level = new_exp // exp_per_level
        leveled_up = new_level > old_level

        # Actualizar experiencia
        await self.set_skills(user_id, **{skill_name: new_exp})

        logger.info(
            "User %d ganó %d exp en %s: %d → %d (nivel %d→%d)",
            user_id,
            exp_gained,
            skill_name,
            current_exp,
            new_exp,
            old_level,
            new_level,
        )

        return new_exp, leveled_up
