"""Task para usar un item del inventario."""

import logging
import struct
from typing import TYPE_CHECKING

from src.inventory_repository import InventoryRepository
from src.items_catalog import get_item
from src.task import Task

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskUseItem(Task):
    """Maneja el uso de items del inventario."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de usar item.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta el uso de un item."""
        # Parsear el packet: PacketID (1 byte) + Slot (1 byte)
        min_packet_size = 2
        if len(self.data) < min_packet_size:
            logger.warning("Packet USE_ITEM inválido: tamaño incorrecto")
            return

        # Verificar que el jugador esté logueado
        user_id_value = self.session_data.get("user_id")
        if not user_id_value or not isinstance(user_id_value, int):
            logger.warning("Intento de usar item sin estar logueado")
            return
        user_id: int = user_id_value

        # Verificar que tengamos player_repo
        if not self.player_repo:
            logger.error("player_repo no disponible")
            return

        try:
            # Extraer el slot del inventario (segundo byte)
            slot = struct.unpack("B", self.data[1:2])[0]

            logger.info("user_id %d intenta usar item en slot %d", user_id, slot)

            # Obtener el inventario
            inventory_repo = InventoryRepository(self.player_repo.redis)
            slot_data = await inventory_repo.get_slot(user_id, slot)

            if not slot_data:
                await self.message_sender.send_console_msg("El slot está vacío.")
                return

            item_id, _quantity = slot_data

            # Obtener el item del catálogo
            item = get_item(item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", item_id)
                await self.message_sender.send_console_msg("Item no válido.")
                return

            # Verificar si el item se puede usar
            if not item.can_use():
                await self.message_sender.send_console_msg(f"No puedes usar {item.name}.")
                return

            # Usar el item
            if item.consumable:
                await self._use_consumable(user_id, slot, item, inventory_repo)
            elif item.equippable:
                await self.message_sender.send_console_msg(
                    f"Equipar items aún no está implementado. Item: {item.name}"
                )

        except struct.error:
            logger.exception("Error al parsear packet USE_ITEM")

    async def _use_consumable(  # type: ignore[no-untyped-def]
        self,
        user_id: int,
        slot: int,
        item,  # noqa: ANN001 - Item from items_catalog
        inventory_repo: InventoryRepository,
    ) -> None:
        """Usa un item consumible.

        Args:
            user_id: ID del jugador.
            slot: Slot del item.
            item: Item a usar.
            inventory_repo: Repositorio de inventario.
        """
        # Aplicar efectos del item
        effects_applied = []

        if item.restore_hp > 0:
            stats = await self.player_repo.get_stats(user_id)  # type: ignore[union-attr]
            if stats:
                new_hp = min(stats["min_hp"] + item.restore_hp, stats["max_hp"])
                stats["min_hp"] = new_hp
                await self.player_repo.set_stats(user_id=user_id, **stats)  # type: ignore[union-attr]
                await self.message_sender.send_update_user_stats(**stats)
                effects_applied.append(f"+{item.restore_hp} HP")

        if item.restore_mana > 0:
            stats = await self.player_repo.get_stats(user_id)  # type: ignore[union-attr]
            if stats:
                new_mana = min(stats["min_mana"] + item.restore_mana, stats["max_mana"])
                stats["min_mana"] = new_mana
                await self.player_repo.set_stats(user_id=user_id, **stats)  # type: ignore[union-attr]
                await self.message_sender.send_update_user_stats(**stats)
                effects_applied.append(f"+{item.restore_mana} Mana")

        if item.restore_hunger > 0 or item.restore_thirst > 0:
            hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)  # type: ignore[union-attr]
            if hunger_thirst:
                if item.restore_hunger > 0:
                    new_hunger = min(
                        hunger_thirst["min_hunger"] + item.restore_hunger,
                        hunger_thirst["max_hunger"],
                    )
                    hunger_thirst["min_hunger"] = new_hunger
                    effects_applied.append(f"+{item.restore_hunger} Hambre")

                if item.restore_thirst > 0:
                    new_water = min(
                        hunger_thirst["min_water"] + item.restore_thirst,
                        hunger_thirst["max_water"],
                    )
                    hunger_thirst["min_water"] = new_water
                    effects_applied.append(f"+{item.restore_thirst} Sed")

                await self.player_repo.set_hunger_thirst(user_id=user_id, **hunger_thirst)  # type: ignore[union-attr]
                await self.message_sender.send_update_hunger_and_thirst(
                    max_water=hunger_thirst["max_water"],
                    min_water=hunger_thirst["min_water"],
                    max_hunger=hunger_thirst["max_hunger"],
                    min_hunger=hunger_thirst["min_hunger"],
                )

        # Remover el item del inventario
        await inventory_repo.remove_item(user_id, slot, 1)

        # Notificar al jugador
        effects_str = ", ".join(effects_applied) if effects_applied else "ningún efecto"
        await self.message_sender.send_console_msg(f"Usaste {item.name}. Efectos: {effects_str}")

        logger.info("user_id %d usó %s (slot %d)", user_id, item.name, slot)
