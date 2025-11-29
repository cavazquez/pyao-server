"""Repositorio para gestionar el libro de hechizos de los jugadores en Redis."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from src.utils.redis_config import RedisKeys
from src.utils.redis_decorators import require_redis

if TYPE_CHECKING:
    from src.models.spell_catalog import SpellCatalog
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MoveSpellResult:
    """Resultado de mover un hechizo dentro del libro."""

    success: bool
    slot: int
    target_slot: int
    slot_spell_id: int | None
    target_slot_spell_id: int | None
    reason: str | None = None


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

    @require_redis(default_return=False)
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

        try:
            key = RedisKeys.player_spellbook(user_id)
            await cast("Any", self.redis).hset(key, str(slot), str(spell_id))
            logger.debug("Hechizo %d agregado al slot %d del user_id %d", spell_id, slot, user_id)
        except Exception:
            logger.exception("Error al agregar hechizo al libro")
            return False
        else:
            return True

    @require_redis(default_return=False)
    async def remove_spell(self, user_id: int, slot: int) -> bool:
        """Elimina un hechizo del libro de hechizos del jugador.

        Args:
            user_id: ID del usuario.
            slot: Slot del hechizo a eliminar.

        Returns:
            True si se eliminó correctamente, False en caso contrario.
        """
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

    @require_redis(default_return=None)
    async def get_spell_in_slot(self, user_id: int, slot: int) -> int | None:
        """Obtiene el ID del hechizo en un slot específico.

        Args:
            user_id: ID del usuario.
            slot: Slot del hechizo.

        Returns:
            ID del hechizo o None si el slot está vacío.
        """
        try:
            key = RedisKeys.player_spellbook(user_id)
            spell_id_str = await cast("Any", self.redis).hget(key, str(slot))
            if spell_id_str:
                return int(spell_id_str)
        except Exception:
            logger.exception("Error al obtener hechizo del slot %d", slot)
        return None

    @require_redis(default_return=cast("dict[int, int]", {}))
    async def get_all_spells(self, user_id: int) -> dict[int, int]:
        """Obtiene todos los hechizos del libro del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con slot -> spell_id.
        """
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

    @require_redis(default_return=None)
    async def move_spell(
        self,
        user_id: int,
        slot: int,
        upwards: bool,
        max_slot: int = 35,
    ) -> MoveSpellResult | None:
        """Intercambia el hechizo en ``slot`` con el adyacente.

        Args:
            user_id: ID del usuario.
            slot: Slot del hechizo a mover (1-based).
            upwards: True para mover hacia arriba (slot-1), False hacia abajo (slot+1).
            max_slot: Límite superior de slots válidos.

        Returns:
            MoveSpellResult con información del intercambio, o None si Redis no está disponible.
        """
        if not 1 <= slot <= max_slot:
            logger.debug("Slot inválido para mover hechizo: %d", slot)
            return MoveSpellResult(
                success=False,
                slot=slot,
                target_slot=slot,
                slot_spell_id=None,
                target_slot_spell_id=None,
                reason="invalid_slot",
            )

        target_slot = slot - 1 if upwards else slot + 1

        if not 1 <= target_slot <= max_slot:
            logger.debug(
                "Movimiento de hechizo fuera de rango: slot=%d, target_slot=%d",
                slot,
                target_slot,
            )
            return MoveSpellResult(
                success=False,
                slot=slot,
                target_slot=target_slot,
                slot_spell_id=None,
                target_slot_spell_id=None,
                reason="out_of_bounds",
            )

        key = RedisKeys.player_spellbook(user_id)

        try:
            pipe = cast("Any", self.redis).pipeline()
            pipe.hget(key, str(slot))
            pipe.hget(key, str(target_slot))
            slot_value, target_value = await pipe.execute()

            new_slot_value = target_value
            new_target_value = slot_value

            pipe = cast("Any", self.redis).pipeline(transaction=True)

            if new_slot_value is None:
                pipe.hdel(key, str(slot))
            else:
                pipe.hset(key, str(slot), str(new_slot_value))

            if new_target_value is None:
                pipe.hdel(key, str(target_slot))
            else:
                pipe.hset(key, str(target_slot), str(new_target_value))

            await pipe.execute()

            slot_spell_id = int(new_slot_value) if new_slot_value is not None else None
            target_spell_id = int(new_target_value) if new_target_value is not None else None

            logger.debug(
                "Hechizos intercambiados para user_id %d: slot %d <-> %d",
                user_id,
                slot,
                target_slot,
            )

            return MoveSpellResult(
                success=True,
                slot=slot,
                target_slot=target_slot,
                slot_spell_id=slot_spell_id,
                target_slot_spell_id=target_spell_id,
            )
        except Exception:
            logger.exception(
                "Error al mover hechizo: user_id=%d, slot=%d, target_slot=%d",
                user_id,
                slot,
                target_slot,
            )
            return MoveSpellResult(
                success=False,
                slot=slot,
                target_slot=target_slot,
                slot_spell_id=None,
                target_slot_spell_id=None,
                reason="error",
            )

    @require_redis(default_return=False)
    async def clear_spellbook(self, user_id: int) -> bool:
        """Limpia todo el libro de hechizos del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            True si se limpió correctamente, False en caso contrario.
        """
        try:
            key = RedisKeys.player_spellbook(user_id)
            await cast("Any", self.redis).delete(key)
            logger.debug("Libro de hechizos limpiado para user_id %d", user_id)
        except Exception:
            logger.exception("Error al limpiar libro de hechizos")
            return False
        else:
            return True

    async def initialize_default_spells(
        self, user_id: int, spell_catalog: SpellCatalog | None = None
    ) -> bool:
        """Inicializa el libro de hechizos con hechizos por defecto.

        Si se proporciona spell_catalog, agrega TODOS los hechizos disponibles del catálogo.
        Si no se proporciona, agrega solo el Dardo Mágico (spell_id=1) en el slot 1.

        Args:
            user_id: ID del usuario.
            spell_catalog: Catálogo de hechizos (opcional).
                Si se proporciona, agrega todos los hechizos.

        Returns:
            True si se inicializó correctamente, False en caso contrario.
        """
        try:
            # Verificar si ya tiene hechizos
            existing_spells: dict[int, int] = await self.get_all_spells(user_id)
            if existing_spells:
                logger.debug("user_id %d ya tiene hechizos en Redis, no se inicializa", user_id)
                return True

            logger.info("Inicializando libro de hechizos por defecto para user_id %d", user_id)

            # Si se proporciona el catálogo, agregar TODOS los hechizos
            if spell_catalog:
                all_spell_ids = spell_catalog.get_all_spell_ids()
                if all_spell_ids:
                    spells_added = 0
                    # Hay 25 slots disponibles (1-25)
                    max_slots = 25
                    if len(all_spell_ids) > max_slots:
                        logger.warning(
                            "Solo se pueden agregar 25 hechizos. "
                            "%d hechizos disponibles en catálogo",
                            len(all_spell_ids),
                        )
                    for slot, spell_id in enumerate(sorted(all_spell_ids)[:max_slots], start=1):
                        success = await self.add_spell(user_id, slot=slot, spell_id=spell_id)
                        if success:
                            spells_added += 1
                            spell_data = spell_catalog.get_spell_data(spell_id)
                            spell_name = (
                                spell_data.get("name", f"Spell {spell_id}")
                                if spell_data
                                else f"Spell {spell_id}"
                            )
                            logger.debug(
                                "✓ Hechizo agregado: user_id %d recibió '%s' (ID:%d) en slot %d",
                                user_id,
                                spell_name,
                                spell_id,
                                slot,
                            )

                    logger.info(
                        "✓ Libro de hechizos inicializado: user_id %d recibió %d hechizo(s) "
                        "del catálogo",
                        user_id,
                        spells_added,
                    )
                    return spells_added > 0
                logger.warning(
                    "Catálogo de hechizos está vacío, agregando Dardo Mágico por defecto"
                )
                # Fallback: agregar Antídoto Mágico si el catálogo está vacío
                success = await self.add_spell(user_id, slot=1, spell_id=1)
                if success:
                    logger.info(
                        "✓ Libro de hechizos inicializado: user_id %d recibió "
                        "'Antídoto Mágico' en slot 1",
                        user_id,
                    )
                return success
            # Comportamiento anterior: solo agregar Antídoto Mágico (ID: 1)
            success = await self.add_spell(user_id, slot=1, spell_id=1)
            if success:
                logger.info(
                    "✓ Libro de hechizos inicializado: user_id %d recibió "
                    "'Antídoto Mágico' en slot 1",
                    user_id,
                )
            return success  # noqa: TRY300
        except Exception:
            logger.exception("Error al inicializar libro de hechizos")
            return False

    async def get_spellbook_for_client(self, user_id: int) -> list[dict[str, Any]]:
        """Obtiene el libro de hechizos formateado para enviar al cliente.

        Args:
            user_id: ID del usuario.

        Returns:
            Lista de diccionarios con información de cada hechizo.
        """
        try:
            spells: dict[int, int] = await self.get_all_spells(user_id)
            result = []
            for slot, spell_id in sorted(spells.items()):
                result.append({"slot": slot, "spell_id": spell_id})
        except Exception:
            logger.exception("Error al obtener libro de hechizos para cliente")
            return []
        else:
            return result
