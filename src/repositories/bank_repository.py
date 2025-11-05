"""Repositorio para gestionar las bóvedas bancarias de los jugadores."""

import logging
from dataclasses import dataclass

from src.repositories.base_slot_repository import BaseSlotRepository
from src.utils.item_slot_parser import ItemSlotParser
from src.utils.redis_client import RedisClient  # noqa: TC001
from src.utils.redis_config import RedisKeys

logger = logging.getLogger(__name__)


@dataclass
class BankItem:
    """Representa un item en la bóveda bancaria."""

    slot: int
    item_id: int
    quantity: int


class BankRepository(BaseSlotRepository):
    """Gestiona las bóvedas bancarias de los jugadores en Redis.

    Cada jugador tiene una bóveda con 20 slots para guardar items.
    Hereda de BaseSlotRepository para reutilizar métodos comunes.
    """

    MAX_SLOTS = 20

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio de banco.

        Args:
            redis_client: Cliente de Redis.
        """
        super().__init__(redis_client)
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
        parsed = await self._get_slot_value(key, slot)

        if not parsed:
            return None

        return BankItem(
            slot=slot,
            item_id=parsed.item_id,
            quantity=parsed.quantity,
        )

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
            slot_num = ItemSlotParser.parse_slot_number(slot_key)
            if slot_num is None:
                continue

            # Parsear item
            parsed = ItemSlotParser.parse(value)
            if parsed:
                items.append(
                    BankItem(
                        slot=slot_num,
                        item_id=parsed.item_id,
                        quantity=parsed.quantity,
                    )
                )

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
        key = RedisKeys.bank(user_id)
        slot = await self._stack_or_add_item(key, item_id, quantity)

        if slot:
            logger.info(
                "user_id %d depositó %d x item_id %d en slot %d del banco",
                user_id,
                quantity,
                item_id,
                slot,
            )
        else:
            logger.warning("user_id %d no tiene espacio en el banco", user_id)

        return slot

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
            await self._clear_slot_by_user(user_id, slot)
            logger.info(
                "user_id %d extrajo %d x item_id %d del slot %d del banco (slot vaciado)",
                user_id,
                quantity,
                bank_item.item_id,
                slot,
            )
        else:
            # Actualizar cantidad
            await self._update_slot_by_user(user_id, slot, bank_item.item_id, new_quantity)
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
        await self._initialize_empty_slots(key)
        logger.info("Bóveda bancaria inicializada para user_id %d", user_id)

    async def _update_slot_by_user(
        self,
        user_id: int,
        slot: int,
        item_id: int,
        quantity: int,
    ) -> None:
        """Actualiza un slot de la bóveda (wrapper para compatibilidad).

        Args:
            user_id: ID del usuario.
            slot: Número de slot (1-20).
            item_id: ID del item.
            quantity: Cantidad.
        """
        key = RedisKeys.bank(user_id)
        await self._update_slot(key, slot, item_id, quantity)

    async def _clear_slot_by_user(self, user_id: int, slot: int) -> None:
        """Vacía un slot de la bóveda (wrapper para compatibilidad).

        Args:
            user_id: ID del usuario.
            slot: Número de slot (1-20).
        """
        key = RedisKeys.bank(user_id)
        await self._clear_slot(key, slot)

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
