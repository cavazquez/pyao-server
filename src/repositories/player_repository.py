"""Repositorio para operaciones de jugadores usando Redis."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
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
        """
        key = RedisKeys.player_user_stats(user_id)
        result: dict[str, str] = await self.redis.redis.hgetall(key)  # type: ignore[misc]

        if not result:
            return None

        return {
            "max_hp": int(result.get("max_hp", 100)),
            "min_hp": int(
                result.get("hp", result.get("min_hp", 100))
            ),  # Priorizar "hp" sobre "min_hp"
            "max_mana": int(result.get("max_mana", 100)),
            "min_mana": int(result.get("min_mana", 100)),
            "max_sta": int(result.get("max_sta", 100)),
            "min_sta": int(result.get("min_sta", 100)),
            "gold": int(result.get("gold", 0)),
            "level": int(result.get("level", 1)),
            "elu": int(result.get("elu", 300)),
            "experience": int(result.get("experience", 0)),
        }

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
        """Establece el estado de meditación del jugador.

        Args:
            user_id: ID del usuario.
            is_meditating: True si está meditando, False si no.
        """
        key = RedisKeys.player_user_stats(user_id)
        logger.info(
            "SET_MEDITATING: user_id=%d, is_meditating=%s, key=%s", user_id, is_meditating, key
        )
        await self.redis.redis.hset(key, "meditating", "1" if is_meditating else "0")  # type: ignore[misc]
        logger.info(
            "Estado de meditación GUARDADO en Redis para user_id %d: %s", user_id, is_meditating
        )

    async def is_meditating(self, user_id: int) -> bool:
        """Verifica si el jugador está meditando.

        Args:
            user_id: ID del usuario.

        Returns:
            True si está meditando, False si no.
        """
        key = RedisKeys.player_user_stats(user_id)
        result = await self.redis.redis.hget(key, "meditating")  # type: ignore[misc]
        # Redis puede retornar bytes (b"1") o string ("1") dependiendo de la configuración
        is_med = result in {b"1", "1", 1} if result else False
        logger.debug(
            "IS_MEDITATING: user_id=%d, result=%s (type=%s), is_meditating=%s",
            user_id,
            result,
            type(result).__name__,
            is_med,
        )
        return is_med

    async def set_sailing(self, user_id: int, is_sailing: bool) -> None:
        """Establece el estado de navegación (barca) del jugador.

        Args:
            user_id: ID del usuario.
            is_sailing: True si está navegando, False si no.
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.redis.hset(key, "sailing", "1" if is_sailing else "0")  # type: ignore[misc]
        logger.info("Estado de navegación guardado para user_id %d: %s", user_id, is_sailing)

    async def is_sailing(self, user_id: int) -> bool:
        """Verifica si el jugador está navegando en barca.

        Args:
            user_id: ID del usuario.

        Returns:
            True si está navegando, False si no.
        """
        key = RedisKeys.player_user_stats(user_id)
        result = await self.redis.redis.hget(key, "sailing")  # type: ignore[misc]
        is_sailing = result in {b"1", "1", 1} if result else False
        logger.debug(
            "IS_SAILING: user_id=%d, result=%s (type=%s), is_sailing=%s",
            user_id,
            result,
            type(result).__name__,
            is_sailing,
        )
        return is_sailing

    async def update_hp(self, user_id: int, hp: int) -> None:
        """Actualiza el HP del jugador.

        Args:
            user_id: ID del usuario.
            hp: Nuevo HP.
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.redis.hset(key, "hp", str(hp))  # type: ignore[misc]
        logger.debug("HP actualizado para user_id %d: %d", user_id, hp)

    async def update_experience(self, user_id: int, exp: int) -> None:
        """Actualiza la experiencia del jugador.

        Args:
            user_id: ID del usuario.
            exp: Nueva experiencia.
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.redis.hset(key, "experience", str(exp))  # type: ignore[misc]
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

    async def get_gold(self, user_id: int) -> int:
        """Obtiene el oro del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Cantidad de oro del jugador.
        """
        key = RedisKeys.player_user_stats(user_id)
        result = await self.redis.redis.hget(key, "gold")  # type: ignore[misc]
        return int(result) if result else 0

    async def update_gold(self, user_id: int, gold: int) -> None:
        """Actualiza el oro del jugador.

        Args:
            user_id: ID del usuario.
            gold: Nuevo oro.
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.redis.hset(key, "gold", str(gold))  # type: ignore[misc]
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
        key = RedisKeys.player_user_stats(user_id)
        result: list[str | None] = await self.redis.redis.hmget(key, ["min_sta", "max_sta"])  # type: ignore[misc]
        min_sta = int(result[0]) if result[0] else 100
        max_sta = int(result[1]) if result[1] else 100
        return (min_sta, max_sta)

    async def update_stamina(self, user_id: int, stamina: int) -> None:
        """Actualiza la stamina actual del jugador.

        Args:
            user_id: ID del usuario.
            stamina: Nueva stamina actual.
        """
        key = RedisKeys.player_user_stats(user_id)
        await self.redis.redis.hset(key, "min_sta", str(stamina))  # type: ignore[misc]
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
