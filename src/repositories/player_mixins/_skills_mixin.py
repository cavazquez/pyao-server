"""Player repository mixins."""

import logging
from typing import TYPE_CHECKING

from src.config.config_manager import ConfigManager, config_manager
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


logger = logging.getLogger(__name__)


class PlayerSkillsMixin:
    """Skill levels and experience."""

    async def get_skills(self, user_id: int) -> dict[str, int] | None:
        """Obtiene las habilidades del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con las habilidades o None si no existe.
        """
        key = RedisKeys.player_skills(user_id)
        result: dict[str, str] = await self.redis.hgetall(key)

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
            await self.redis.hset(key, mapping={k: str(v) for k, v in skills.items()})
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
