"""Persistencia de niveles y XP separados, con incremento transaccional de progreso."""

from typing import TYPE_CHECKING

from redis.exceptions import WatchError

from src.config.config_manager import ConfigManager, config_manager
from src.models.skills import MAX_SKILL_LEVEL, SKILLS_BY_KEY, SkillProgress, skill_progress
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient


class PlayerSkillsMixin:
    """Expone niveles para lógica de juego y progreso completo para la UI."""

    if TYPE_CHECKING:
        redis: RedisClient

    async def get_skill_progress(self, user_id: int) -> list[SkillProgress]:
        """Lee progreso completo sin reescribir datos al enviar.

        Returns:
            Catálogo completo con nivel, XP acumulada y porcentaje.
        """
        values = await self.redis.hgetall(RedisKeys.player_skills(user_id))
        threshold = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
        return skill_progress(values, threshold)

    async def get_skills(self, user_id: int) -> dict[str, int] | None:
        """Obtiene niveles para los consumidores de juego, nunca XP como nivel.

        Returns:
            Diccionario por clave histórica o None si no hay progreso guardado.
        """
        values = await self.redis.hgetall(RedisKeys.player_skills(user_id))
        if not values:
            return None
        threshold = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
        return {
            progress.definition.key: progress.level
            for progress in skill_progress(values, threshold)
            if progress.definition.key is not None
        }

    async def get_skill_points(self, user_id: int) -> int:
        """Lee el presupuesto autoritativo sin conceder puntos desde el cliente.

        Returns:
            Puntos persistidos, o cero para perfiles sin presupuesto.
        """
        value = await self.redis.hget(RedisKeys.player_skills(user_id), "points")
        return int(value or 0)

    async def set_skills(self, user_id: int, **skills: int) -> None:
        """Asigna niveles explícitos, conservando XP existente de forma atómica.

        Raises:
            ValueError: Si una clave o nivel no pertenece al catálogo.
        """
        for name, level in skills.items():
            if name not in SKILLS_BY_KEY or not 0 <= level <= MAX_SKILL_LEVEL:
                msg = "Asignación de nivel de habilidad inválida"
                raise ValueError(msg)
        if not skills:
            return
        key = RedisKeys.player_skills(user_id)
        threshold = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
        async with self.redis.redis.pipeline(transaction=True) as pipe:
            for name, level in skills.items():
                pipe.hset(key, f"level:{name}", str(level))
                pipe.hsetnx(key, f"xp:{name}", "0")
                pipe.hsetnx(key, name, str(level))  # Auditoría del valor inicial/legado.
            pipe.hsetnx(key, "xp_per_level", str(threshold))
            pipe.hsetnx(key, "progress_version", "1")
            await pipe.execute()

    async def add_skill_experience(
        self, user_id: int, skill_name: str, exp_gained: int
    ) -> tuple[int, bool]:
        """Suma XP sin perder incrementos concurrentes ni convertirla en nivel.

        Returns:
            XP acumulada nueva y si cruzó al menos un nivel.

        Raises:
            ValueError: Si la clave o la ganancia no son válidas.
            RuntimeError: Ante contención persistente sin confirmar una escritura.
        """
        if skill_name not in SKILLS_BY_KEY or exp_gained < 1:
            msg = "Ganancia de experiencia inválida"
            raise ValueError(msg)
        key = RedisKeys.player_skills(user_id)
        default = ConfigManager.as_int(config_manager.get("game.work.exp_per_level", 100))
        for _ in range(16):
            async with self.redis.redis.pipeline() as pipe:
                try:
                    await pipe.watch(key)
                    values = await pipe.hgetall(key)
                    progress = next(
                        p for p in skill_progress(values, default) if p.definition.key == skill_name
                    )
                    threshold = int(values.get("xp_per_level", default))
                    new_exp = progress.experience + exp_gained
                    crossed = new_exp // threshold - progress.experience // threshold
                    new_level = min(MAX_SKILL_LEVEL, progress.level + crossed)
                    pipe.multi()
                    pipe.hset(
                        key,
                        mapping={
                            f"level:{skill_name}": str(new_level),
                            f"xp:{skill_name}": str(new_exp),
                        },
                    )
                    pipe.hsetnx(key, "xp_per_level", str(threshold))
                    pipe.hsetnx(key, "progress_version", "1")
                    await pipe.execute()
                except WatchError:
                    continue
                else:
                    return new_exp, new_level > progress.level
        msg = "No se pudo confirmar la experiencia por contención"
        raise RuntimeError(msg)
