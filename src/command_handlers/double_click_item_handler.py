"""Handler especializado para doble click en items del inventario."""

import logging
from typing import TYPE_CHECKING, Any

from src.models.items_catalog import get_item
from src.repositories.inventory_repository import InventoryRepository

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class DoubleClickItemHandler:
    """Handler especializado para doble click en items del inventario."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de items.

        Args:
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.message_sender = message_sender

    async def handle_item_use(
        self, user_id: int, slot: int
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Maneja el uso de un item del inventario.

        Args:
            user_id: ID del usuario.
            slot: Slot del inventario.

        Returns:
            Tupla (success, error_message, result_data).
        """
        logger.info("user_id %d intenta usar item en slot %d", user_id, slot)

        # Crear inventory_repo desde player_repo.redis
        player_redis = getattr(self.player_repo, "redis", None)
        if not player_redis:
            logger.error("inventory_repo no disponible")
            return False, "Error interno: repositorio no disponible", None

        inventory_repo = InventoryRepository(player_redis)
        slot_data = await inventory_repo.get_slot(user_id, slot)

        if not slot_data:
            await self.message_sender.send_console_msg("El slot está vacío.")
            return False, "El slot está vacío", None

        item_id, _quantity = slot_data

        # Obtener el item del catálogo
        item = get_item(item_id)
        if not item:
            logger.error("Item %d no encontrado en catálogo", item_id)
            await self.message_sender.send_console_msg("Item no válido.")
            return False, "Item no válido", None

        # Verificar si el item se puede usar
        if not item.can_use():
            await self.message_sender.send_console_msg(f"No puedes usar {item.name}.")
            return False, f"No puedes usar {item.name}", None

        # Usar el item
        if item.consumable:
            return await self._use_consumable(user_id, slot, item, inventory_repo)
        if item.equippable:
            await self.message_sender.send_console_msg(
                f"Equipar items aún no está implementado. Item: {item.name}"
            )
            return False, "Equipar items aún no está implementado", None

        return False, "Item no se puede usar", None

    async def _use_consumable(  # type: ignore[no-untyped-def]
        self,
        user_id: int,
        slot: int,
        item,  # noqa: ANN001 - Item from items_catalog
        inventory_repo: InventoryRepository,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Usa un item consumible.

        Args:
            user_id: ID del jugador.
            slot: Slot del item.
            item: Item a usar.
            inventory_repo: Repositorio de inventario.

        Returns:
            Tupla (success, error_message, result_data).
        """
        # Aplicar efectos del item
        effects_applied = []

        if item.restore_hp > 0:
            current_hp = await self.player_repo.get_current_hp(user_id)
            max_hp = await self.player_repo.get_max_hp(user_id)
            new_hp = min(current_hp + item.restore_hp, max_hp)
            await self.player_repo.update_hp(user_id, new_hp)

            # Obtener stats actualizados para enviar al cliente
            stats = await self.player_repo.get_stats(user_id)
            if stats:
                await self.message_sender.send_update_user_stats(**stats)
            effects_applied.append(f"+{item.restore_hp} HP")

        if item.restore_mana > 0:
            min_mana, max_mana = await self.player_repo.get_mana(user_id)
            new_mana = min(min_mana + item.restore_mana, max_mana)
            await self.player_repo.update_mana(user_id, new_mana)

            # Obtener stats actualizados para enviar al cliente
            stats = await self.player_repo.get_stats(user_id)
            if stats:
                await self.message_sender.send_update_user_stats(**stats)
            effects_applied.append(f"+{item.restore_mana} Mana")

        if item.restore_hunger > 0 or item.restore_thirst > 0:
            hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)
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

                await self.player_repo.set_hunger_thirst(user_id=user_id, **hunger_thirst)
                await self.message_sender.send_update_hunger_and_thirst(
                    max_water=hunger_thirst["max_water"],
                    min_water=hunger_thirst["min_water"],
                    max_hunger=hunger_thirst["max_hunger"],
                    min_hunger=hunger_thirst["min_hunger"],
                )

        # Remover el item del inventario
        removed = await inventory_repo.remove_item(user_id, slot, 1)

        if not removed:
            logger.warning("No se pudo consumir el item en slot %d para user_id %d", slot, user_id)
            return False, "No se pudo consumir el item", None

        # Actualizar slot en cliente
        updated_slot = await inventory_repo.get_slot(user_id, slot)

        if not updated_slot:
            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=0,
                name="",
                amount=0,
                equipped=False,
                grh_id=0,
                item_type=0,
                max_hit=0,
                min_hit=0,
                max_def=0,
                min_def=0,
                sale_price=0.0,
            )
        else:
            remaining_quantity = updated_slot[1]
            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=item.item_id,
                name=item.name,
                amount=remaining_quantity,
                equipped=False,
                grh_id=item.graphic_id,
                item_type=item.item_type.to_client_type(),
                max_hit=item.max_damage or 0,
                min_hit=item.min_damage or 0,
                max_def=item.defense or 0,
                min_def=item.defense or 0,
                sale_price=float(item.value),
            )

        # Notificar al jugador
        effects_str = ", ".join(effects_applied) if effects_applied else "ningún efecto"
        await self.message_sender.send_console_msg(f"Usaste {item.name}. Efectos: {effects_str}")

        logger.info("user_id %d usó %s (slot %d)", user_id, item.name, slot)

        return (
            True,
            None,
            {
                "item_id": item.item_id,
                "item_name": item.name,
                "slot": slot,
                "effects": effects_applied,
            },
        )
