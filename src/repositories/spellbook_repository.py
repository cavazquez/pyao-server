"""Repositorio para gestionar el libro de hechizos de los jugadores en Redis."""

import logging
from typing import TYPE_CHECKING, Any, cast

from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class SpellbookRepository:
    """Gestiona el libro de hechizos de los jugadores en Redis."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio de libro de hechizos.

        Args:
            redis_client: Cliente de Redis (RedisClient wrapper).
        """
        self.redis_client = redis_client
        # Acceder al cliente Redis interno
        self.redis = redis_client.redis

    async def add_spell(self, user_id: int, slot: int, spell_id: int) -> bool:
        """Agrega un hechizo al libro de hechizos del jugador.

        Args:
            user_id: ID del usuario.
            slot: Slot donde se guardará el hechizo (1-25).
            spell_id: ID del hechizo.

        Returns:
            True si se agregó correctamente, False en caso contrario.
        """
        if not 1 <= slot <= 25:  # noqa: PLR2004
            logger.warning("Slot inválido: %d (debe estar entre 1 y 25)", slot)
            return False

        if self.redis is None:
            logger.error("Cliente Redis no disponible")
            return False

        try:
            key = RedisKeys.player_spellbook(user_id)
            await cast("Any", self.redis).hset(key, str(slot), str(spell_id))
            logger.debug("Hechizo %d agregado al slot %d del user_id %d", spell_id, slot, user_id)
        except Exception:
            logger.exception("Error al agregar hechizo al libro")
            return False
        else:
            return True

    async def remove_spell(self, user_id: int, slot: int) -> bool:
        """Elimina un hechizo del libro de hechizos del jugador.

        Args:
            user_id: ID del usuario.
            slot: Slot del hechizo a eliminar.

        Returns:
            True si se eliminó correctamente, False en caso contrario.
        """
        if self.redis is None:
            logger.error("Cliente Redis no disponible")
            return False

        try:
            key = RedisKeys.player_spellbook(user_id)
            result = await cast("Any", self.redis).hdel(key, str(slot))
            if result > 0:
                logger.debug("Hechizo eliminado del slot %d del user_id %d", slot, user_id)
                return True
            logger.debug("No había hechizo en el slot %d del user_id %d", slot, user_id)
        except Exception:
            logger.exception("Error al eliminar hechizo del libro")
        return False

    async def get_spell_in_slot(self, user_id: int, slot: int) -> int | None:
        """Obtiene el ID del hechizo en un slot específico.

        Args:
            user_id: ID del usuario.
            slot: Slot del hechizo.

        Returns:
            ID del hechizo o None si el slot está vacío.
        """
        if self.redis is None:
            logger.error("Cliente Redis no disponible")
            return None

        try:
            key = RedisKeys.player_spellbook(user_id)
            spell_id_str = await cast("Any", self.redis).hget(key, str(slot))
            if spell_id_str:
                return int(spell_id_str)
        except Exception:
            logger.exception("Error al obtener hechizo del slot %d", slot)
        return None

    async def get_all_spells(self, user_id: int) -> dict[int, int]:
        """Obtiene todos los hechizos del libro del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con slot -> spell_id.
        """
        if self.redis is None:
            logger.error("Cliente Redis no disponible")
            return {}

        try:
            key = RedisKeys.player_spellbook(user_id)
            spells_data = await cast("Any", self.redis).hgetall(key)
            if not spells_data:
                return {}

            # Convertir strings a int
            return {int(slot): int(spell_id) for slot, spell_id in spells_data.items()}
        except Exception:
            logger.exception("Error al obtener todos los hechizos del user_id %d", user_id)
            return {}

    async def clear_spellbook(self, user_id: int) -> bool:
        """Limpia todo el libro de hechizos del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            True si se limpió correctamente, False en caso contrario.
        """
        if self.redis is None:
            logger.error("Cliente Redis no disponible")
            return False

        try:
            key = RedisKeys.player_spellbook(user_id)
            await cast("Any", self.redis).delete(key)
            logger.debug("Libro de hechizos limpiado para user_id %d", user_id)
        except Exception:
            logger.exception("Error al limpiar libro de hechizos")
            return False
        else:
            return True

    async def initialize_default_spells(self, user_id: int) -> bool:
        """Inicializa el libro de hechizos con hechizos por defecto.

        Por ahora, solo agrega el Dardo Mágico (spell_id=1) en el slot 1.

        Args:
            user_id: ID del usuario.

        Returns:
            True si se inicializó correctamente, False en caso contrario.
        """
        try:
            # Verificar si ya tiene hechizos
            existing_spells = await self.get_all_spells(user_id)
            if existing_spells:
                logger.debug("user_id %d ya tiene hechizos en Redis, no se inicializa", user_id)
                return True

            # Agregar Dardo Mágico en slot 1
            logger.info("Inicializando libro de hechizos por defecto para user_id %d", user_id)
            success = await self.add_spell(user_id, slot=1, spell_id=1)
            if success:
                logger.info(
                    "✓ Libro de hechizos inicializado: user_id %d recibió 'Dardo Mágico' en slot 1",
                    user_id,
                )
        except Exception:
            logger.exception("Error al inicializar libro de hechizos")
            return False
        else:
            return success

    async def get_spellbook_for_client(self, user_id: int) -> list[dict[str, Any]]:
        """Obtiene el libro de hechizos formateado para enviar al cliente.

        Args:
            user_id: ID del usuario.

        Returns:
            Lista de diccionarios con información de cada hechizo.
        """
        try:
            spells = await self.get_all_spells(user_id)
            result = []
            for slot, spell_id in sorted(spells.items()):
                result.append({"slot": slot, "spell_id": spell_id})
        except Exception:
            logger.exception("Error al obtener libro de hechizos para cliente")
            return []
        else:
            return result
