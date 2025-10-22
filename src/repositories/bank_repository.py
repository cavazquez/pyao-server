"""Repositorio para gestionar las bóvedas bancarias de los jugadores."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


@dataclass
class BankItem:
    """Representa un item en la bóveda bancaria."""

    slot: int
    item_id: int
    quantity: int


class BankRepository:
    """Gestiona las bóvedas bancarias de los jugadores en Redis.

    Cada jugador tiene una bóveda con 20 slots para guardar items.
    """

    MAX_SLOTS = 20

    def __init__(self, redis_client: "RedisClient") -> None:
        """Inicializa el repositorio de banco.

        Args:
            redis_client: Cliente de Redis.
        """
        self.redis_client = redis_client

    async def get_bank(self, user_id: int) -> dict[str, str]:
        """Obtiene toda la bóveda bancaria del jugador.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con los slots del banco (slot_N: "item_id:quantity").
        """
        key = RedisKeys.bank(user_id)
        bank = await self.redis_client.redis.hgetall(key)  # type: ignore[misc]

        # Si no existe, inicializar bóveda vacía
        if not bank:
            await self._initialize_empty_bank(user_id)
            bank = await self.redis_client.redis.hgetall(key)  # type: ignore[misc]

        return bank  # type: ignore[no-any-return]

    async def get_item(self, user_id: int, slot: int) -> BankItem | None:
        """Obtiene un item específico de la bóveda.

        Args:
            user_id: ID del usuario.
            slot: Número de slot (1-20).

        Returns:
            BankItem o None si el slot está vacío.
        """
        if slot < 1 or slot > self.MAX_SLOTS:
            logger.warning("Slot inválido: %d", slot)
            return None

        key = RedisKeys.bank(user_id)
        slot_key = f"slot_{slot}"
        value = await self.redis_client.redis.hget(key, slot_key)  # type: ignore[misc]

        if not value:
            return None

        # Parsear "item_id:quantity"
        try:
            item_id_str, quantity_str = value.split(":")
            return BankItem(
                slot=slot,
                item_id=int(item_id_str),
                quantity=int(quantity_str),
            )
        except (ValueError, AttributeError):
            logger.exception("Error parseando slot %d del banco de user_id %d", slot, user_id)
            return None

    async def get_all_items(self, user_id: int) -> list[BankItem]:
        """Obtiene todos los items de la bóveda.

        Args:
            user_id: ID del usuario.

        Returns:
            Lista de BankItem con todos los items en el banco.
        """
        bank = await self.get_bank(user_id)
        items: list[BankItem] = []

        for slot_key, value in bank.items():
            if not value:
                continue

            # Extraer número de slot
            try:
                slot_num = int(str(slot_key).split("_")[1])
            except (IndexError, ValueError):
                continue

            # Parsear item
            try:
                item_id_str, quantity_str = str(value).split(":")
                items.append(
                    BankItem(
                        slot=slot_num,
                        item_id=int(item_id_str),
                        quantity=int(quantity_str),
                    )
                )
            except (ValueError, AttributeError):
                logger.exception("Error parseando item del banco de user_id %d", user_id)
                continue

        return items

    async def deposit_item(self, user_id: int, item_id: int, quantity: int) -> int | None:
        """Deposita un item en la bóveda.

        Busca un slot vacío o apila con items existentes del mismo tipo.

        Args:
            user_id: ID del usuario.
            item_id: ID del item.
            quantity: Cantidad a depositar.

        Returns:
            Número de slot donde se depositó, o None si no hay espacio.
        """
        bank = await self.get_bank(user_id)

        # Buscar si ya existe el item para apilar
        for slot in range(1, self.MAX_SLOTS + 1):
            slot_key = f"slot_{slot}"
            value = bank.get(slot_key, "")

            if value:
                try:
                    existing_id_str, existing_qty_str = value.split(":")
                    existing_id = int(existing_id_str)
                    existing_qty = int(existing_qty_str)

                    if existing_id == item_id:
                        # Apilar con item existente
                        new_quantity = existing_qty + quantity
                        await self._update_slot(user_id, slot, item_id, new_quantity)
                        logger.info(
                            "user_id %d depositó %d x item_id %d en slot %d del banco (apilado)",
                            user_id,
                            quantity,
                            item_id,
                            slot,
                        )
                        return slot
                except (ValueError, AttributeError):
                    continue

        # Buscar slot vacío
        for slot in range(1, self.MAX_SLOTS + 1):
            slot_key = f"slot_{slot}"
            value = bank.get(slot_key, "")

            if not value:
                await self._update_slot(user_id, slot, item_id, quantity)
                logger.info(
                    "user_id %d depositó %d x item_id %d en slot %d del banco",
                    user_id,
                    quantity,
                    item_id,
                    slot,
                )
                return slot

        logger.warning("user_id %d no tiene espacio en el banco", user_id)
        return None

    async def extract_item(self, user_id: int, slot: int, quantity: int) -> bool:
        """Extrae un item de la bóveda.

        Args:
            user_id: ID del usuario.
            slot: Número de slot (1-20).
            quantity: Cantidad a extraer.

        Returns:
            True si se extrajo correctamente, False en caso contrario.
        """
        bank_item = await self.get_item(user_id, slot)

        if not bank_item:
            logger.warning("user_id %d intentó extraer de slot %d vacío", user_id, slot)
            return False

        if bank_item.quantity < quantity:
            logger.warning(
                "user_id %d intentó extraer %d items pero solo tiene %d",
                user_id,
                quantity,
                bank_item.quantity,
            )
            return False

        new_quantity = bank_item.quantity - quantity

        if new_quantity == 0:
            # Vaciar slot
            await self._clear_slot(user_id, slot)
            logger.info(
                "user_id %d extrajo %d x item_id %d del slot %d del banco (slot vaciado)",
                user_id,
                quantity,
                bank_item.item_id,
                slot,
            )
        else:
            # Actualizar cantidad
            await self._update_slot(user_id, slot, bank_item.item_id, new_quantity)
            logger.info(
                "user_id %d extrajo %d x item_id %d del slot %d del banco (%d restantes)",
                user_id,
                quantity,
                bank_item.item_id,
                slot,
                new_quantity,
            )

        return True

    async def _initialize_empty_bank(self, user_id: int) -> None:
        """Inicializa una bóveda vacía para el jugador.

        Args:
            user_id: ID del usuario.
        """
        key = RedisKeys.bank(user_id)
        bank_data = {f"slot_{i}": "" for i in range(1, self.MAX_SLOTS + 1)}
        await self.redis_client.redis.hset(key, mapping=bank_data)  # type: ignore[misc]
        logger.info("Bóveda bancaria inicializada para user_id %d", user_id)

    async def _update_slot(
        self,
        user_id: int,
        slot: int,
        item_id: int,
        quantity: int,
    ) -> None:
        """Actualiza un slot de la bóveda.

        Args:
            user_id: ID del usuario.
            slot: Número de slot (1-20).
            item_id: ID del item.
            quantity: Cantidad.
        """
        key = RedisKeys.bank(user_id)
        slot_key = f"slot_{slot}"
        value = f"{item_id}:{quantity}"
        await self.redis_client.redis.hset(key, slot_key, value)  # type: ignore[misc]

    async def _clear_slot(self, user_id: int, slot: int) -> None:
        """Vacía un slot de la bóveda.

        Args:
            user_id: ID del usuario.
            slot: Número de slot (1-20).
        """
        key = RedisKeys.bank(user_id)
        slot_key = f"slot_{slot}"
        await self.redis_client.redis.hset(key, slot_key, "")  # type: ignore[misc]

    async def get_gold(self, user_id: int) -> int:
        """Obtiene la cantidad de oro almacenado en el banco.

        Args:
            user_id: ID del usuario.

        Returns:
            Cantidad de oro en el banco (0 si no hay).
        """
        key = RedisKeys.bank_gold(user_id)
        gold = await self.redis_client.redis.get(key)
        if gold is None:
            return 0
        try:
            return int(gold)
        except (ValueError, TypeError):
            logger.warning("Oro inválido en banco de user_id %d: %s", user_id, gold)
            return 0

    async def add_gold(self, user_id: int, amount: int) -> int:
        """Agrega oro al banco del jugador.

        Args:
            user_id: ID del usuario.
            amount: Cantidad de oro a agregar (debe ser positivo).

        Returns:
            Nueva cantidad total de oro en el banco.
        """
        if amount <= 0:
            logger.warning("Intento de agregar cantidad inválida de oro: %d", amount)
            return await self.get_gold(user_id)

        key = RedisKeys.bank_gold(user_id)
        new_gold = await self.redis_client.redis.incrby(key, amount)
        logger.info("user_id %d depositó %d oro en banco. Total: %d", user_id, amount, new_gold)
        return int(new_gold)

    async def remove_gold(self, user_id: int, amount: int) -> bool:
        """Retira oro del banco del jugador.

        Args:
            user_id: ID del usuario.
            amount: Cantidad de oro a retirar (debe ser positivo).

        Returns:
            True si se pudo retirar, False si no hay suficiente oro.
        """
        if amount <= 0:
            logger.warning("Intento de retirar cantidad inválida de oro: %d", amount)
            return False

        current_gold = await self.get_gold(user_id)
        if current_gold < amount:
            logger.debug(
                "user_id %d no tiene suficiente oro en banco: tiene %d, intenta retirar %d",
                user_id,
                current_gold,
                amount,
            )
            return False

        key = RedisKeys.bank_gold(user_id)
        new_gold = await self.redis_client.redis.decrby(key, amount)
        logger.info("user_id %d retiró %d oro del banco. Restante: %d", user_id, amount, new_gold)
        return True
