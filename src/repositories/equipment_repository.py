"""Repositorio para gestionar el equipamiento de los jugadores en Redis."""

import logging
from typing import TYPE_CHECKING, Any, cast

from src.utils.equipment_slot import EquipmentSlot
from src.utils.redis_config import RedisKeys
from src.utils.redis_decorators import require_redis

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class EquipmentRepository:
    """Gestiona el equipamiento de los jugadores en Redis."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio de equipamiento.

        Args:
            redis_client: Cliente de Redis (RedisClient wrapper).
        """
        self.redis_client = redis_client
        # Acceder al cliente Redis interno
        self.redis = redis_client.redis

    @require_redis(default_return=False)
    async def equip_item(self, user_id: int, slot: EquipmentSlot, inventory_slot: int) -> bool:
        """Equipa un item en un slot específico.

        Args:
            user_id: ID del usuario.
            slot: Slot de equipamiento.
            inventory_slot: Slot del inventario donde está el item.

        Returns:
            True si se equipó correctamente, False en caso contrario.
        """
        try:
            key = RedisKeys.player_equipment(user_id)
            await cast("Any", self.redis).hset(key, slot.value, str(inventory_slot))
            logger.info(
                "Item equipado: user_id=%d, slot=%s, inventory_slot=%d",
                user_id,
                slot.value,
                inventory_slot,
            )
        except Exception:
            logger.exception("Error al equipar item")
            return False
        else:
            return True

    @require_redis(default_return=False)
    async def unequip_item(self, user_id: int, slot: EquipmentSlot) -> bool:
        """Desequipa un item de un slot específico.

        Args:
            user_id: ID del usuario.
            slot: Slot de equipamiento.

        Returns:
            True si se desequipó correctamente, False en caso contrario.
        """
        try:
            key = RedisKeys.player_equipment(user_id)
            result = await cast("Any", self.redis).hdel(key, slot.value)
            if result > 0:
                logger.info("Item desequipado: user_id=%d, slot=%s", user_id, slot.value)
                return True
            logger.debug("No había item equipado en slot %s del user_id %d", slot.value, user_id)
        except Exception:
            logger.exception("Error al desequipar item")
        return False

    @require_redis(default_return=None)
    async def get_equipped_slot(self, user_id: int, slot: EquipmentSlot) -> int | None:
        """Obtiene el slot del inventario del item equipado en un slot específico.

        Args:
            user_id: ID del usuario.
            slot: Slot de equipamiento.

        Returns:
            Slot del inventario donde está el item equipado o None si no hay nada equipado.
        """
        try:
            key = RedisKeys.player_equipment(user_id)
            inventory_slot_str = await cast("Any", self.redis).hget(key, slot.value)
            if inventory_slot_str:
                return int(inventory_slot_str)
        except Exception:
            logger.exception("Error al obtener item equipado del slot %s", slot.value)
        return None

    @require_redis(default_return=cast("dict[EquipmentSlot, int]", {}))
    async def get_all_equipment(self, user_id: int) -> dict[EquipmentSlot, int]:
        """Obtiene todo el equipamiento del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con slot de equipamiento -> slot del inventario.
        """
        try:
            key = RedisKeys.player_equipment(user_id)
            equipment_data = await cast("Any", self.redis).hgetall(key)
            if not equipment_data:
                return {}

            # Convertir strings a EquipmentSlot y int
            result = {}
            for slot_name, inventory_slot_str in equipment_data.items():
                try:
                    slot = EquipmentSlot(slot_name)
                    result[slot] = int(inventory_slot_str)
                except (ValueError, KeyError):
                    logger.warning("Slot de equipamiento inválido: %s", slot_name)
                    continue

        except Exception:
            logger.exception("Error al obtener todo el equipamiento del user_id %d", user_id)
            return {}
        else:
            return result

    async def is_slot_equipped(self, user_id: int, inventory_slot: int) -> EquipmentSlot | None:
        """Verifica si un slot del inventario está equipado y en qué slot de equipamiento.

        Args:
            user_id: ID del usuario.
            inventory_slot: Slot del inventario a verificar.

        Returns:
            Slot de equipamiento donde está equipado o None si no está equipado.
        """
        equipment: dict[EquipmentSlot, int] = await self.get_all_equipment(user_id)
        for eq_slot, inv_slot in equipment.items():
            if inv_slot == inventory_slot:
                return eq_slot
        return None

    @require_redis(default_return=False)
    async def clear_equipment(self, user_id: int) -> bool:
        """Limpia todo el equipamiento del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            True si se limpió correctamente, False en caso contrario.
        """
        try:
            key = RedisKeys.player_equipment(user_id)
            await cast("Any", self.redis).delete(key)
            logger.debug("Equipamiento limpiado para user_id %d", user_id)
        except Exception:
            logger.exception("Error al limpiar equipamiento")
            return False
        else:
            return True
