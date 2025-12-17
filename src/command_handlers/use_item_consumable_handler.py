"""Handler especializado para items consumibles (pociones, comida)."""

import logging
import random
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

from src.commands.base import CommandResult
from src.models.item_types import TipoPocion
from src.models.items_catalog import get_item

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import (
        MultiplayerBroadcastService,
    )

logger = logging.getLogger(__name__)


class UseItemConsumableHandler:
    """Handler especializado para items consumibles (pociones, comida)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
        item_catalog: ItemCatalog | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        map_manager: MapManager | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Inicializa el handler de consumibles.

        Args:
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes.
            item_catalog: Catálogo de items (para datos completos de pociones).
            broadcast_service: Servicio de broadcast multijugador (para invisibilidad).
            map_manager: Gestor de mapas (para obtener message senders).
            account_repo: Repositorio de cuentas (para invisibilidad).
        """
        self.player_repo = player_repo
        self.message_sender = message_sender
        self.item_catalog = item_catalog
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager
        self.account_repo = account_repo

    async def handle_apple(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
        slot: int,
        inventory_repo: InventoryRepository,
    ) -> CommandResult:
        """Maneja el consumo de manzanas.

        Returns:
            Resultado de la ejecución.
        """
        logger.info("Consumiendo manzana del slot %d", slot)

        # Consumir una manzana utilizando la API del repositorio
        if quantity <= 1:
            await inventory_repo.clear_slot(user_id, slot)
        else:
            removed = await inventory_repo.remove_item(user_id, slot, 1)
            if not removed:
                logger.warning(
                    "No se pudo decrementar la cantidad del slot %d para el ítem %d",
                    slot,
                    item_id,
                )
                return CommandResult.error("No se pudo consumir el item")

        # Restaurar hambre utilizando la API de hambre/sed
        hunger_restored = await self._restore_hunger(user_id)
        if not hunger_restored:
            return CommandResult.error("No se pudo restaurar el hambre")

        await self.message_sender.send_console_msg("¡Has comido una manzana!")

        # Actualizar el slot en el cliente
        await self._update_inventory_slot_after_consumption(user_id, item_id, slot, inventory_repo)

        return CommandResult.ok(
            data={"item_id": item_id, "quantity_remaining": quantity - 1, "handled": True}
        )

    async def handle_potion(
        self,
        user_id: int,
        item_id: int,
        quantity: int,
        slot: int,
        inventory_repo: InventoryRepository,
        item_data: dict[str, object],
        potion_type: int,
    ) -> CommandResult:
        """Maneja el consumo de una poción.

        Args:
            user_id: ID del jugador.
            item_id: ID del item (poción).
            quantity: Cantidad actual del item.
            slot: Slot del inventario.
            inventory_repo: Repositorio de inventario.
            item_data: Datos completos del item desde TOML.
            potion_type: Tipo de poción (TipoPocion enum value).

        Returns:
            Resultado de la ejecución.
        """
        # Consumir la poción
        if quantity <= 1:
            await inventory_repo.clear_slot(user_id, slot)
        else:
            removed = await inventory_repo.remove_item(user_id, slot, 1)
            if not removed:
                logger.warning(
                    "No se pudo consumir poción user_id=%d item_id=%d slot=%d",
                    user_id,
                    item_id,
                    slot,
                )
                return CommandResult.error("No se pudo consumir la poción")

        # Aplicar efectos según el tipo de poción
        if potion_type == TipoPocion.HP:  # Tipo 3: Restaura HP
            await self._handle_hp_potion(user_id, item_data)

        elif potion_type == TipoPocion.MANA:  # Tipo 4: Restaura Mana
            await self._handle_mana_potion(user_id, item_data)

        elif potion_type == TipoPocion.AGILIDAD:  # Tipo 1: Modifica Agilidad
            await self._handle_agility_potion(user_id, item_data)

        elif potion_type == TipoPocion.FUERZA:  # Tipo 2: Modifica Fuerza
            await self._handle_strength_potion(user_id, item_data)

        elif potion_type == TipoPocion.CURA_VENENO:  # Tipo 5: Cura Veneno
            await self._handle_cure_poison_potion(user_id)

        elif potion_type == TipoPocion.INVISIBLE:  # Tipo 6: Invisibilidad
            await self._handle_invisibility_potion(user_id)

        else:
            logger.warning("Tipo de poción desconocido: %d para item_id %d", potion_type, item_id)
            await self.message_sender.send_console_msg("Esta poción no tiene efecto.")
            return CommandResult.error(f"Tipo de poción desconocido: {potion_type}")

        # Actualizar el slot en el cliente
        await self._update_inventory_slot_after_consumption(user_id, item_id, slot, inventory_repo)

        potion_name = item_data.get("Name", "Poción")
        await self.message_sender.send_console_msg(f"¡Has usado {potion_name}!")

        logger.info(
            "Poción consumida: user_id=%d item_id=%d tipo=%d slot=%d",
            user_id,
            item_id,
            potion_type,
            slot,
        )

        return CommandResult.ok(
            data={"item_id": item_id, "quantity_remaining": quantity - 1, "handled": True}
        )

    async def _restore_hunger(self, user_id: int) -> bool:
        """Restaura el hambre del jugador.

        Returns:
            True si se restauró exitosamente, False en caso contrario.
        """
        if not self.player_repo:
            return False

        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)
        if not hunger_thirst:
            logger.warning("No se encontraron datos de hambre/sed para user_id %d", user_id)
            await self.message_sender.send_console_msg("No se pudo restaurar el hambre.")
            return False

        current_hunger = hunger_thirst.get("min_hunger", 0)
        max_hunger = hunger_thirst.get("max_hunger", 100)
        new_hunger = min(current_hunger + 20, max_hunger)
        hunger_thirst["min_hunger"] = new_hunger

        # Mantener flags y contadores tal como están para no interferir con el tick
        await self.player_repo.set_hunger_thirst(user_id=user_id, **hunger_thirst)

        await self.message_sender.send_update_hunger_and_thirst(
            max_water=hunger_thirst.get("max_water", 0),
            min_water=hunger_thirst.get("min_water", 0),
            max_hunger=max_hunger,
            min_hunger=new_hunger,
        )
        return True

    async def _update_inventory_slot_after_consumption(
        self, user_id: int, item_id: int, slot: int, inventory_repo: InventoryRepository
    ) -> None:
        """Actualiza el slot del inventario después de consumir un ítem."""
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
            _, remaining_quantity = updated_slot
            catalog_item = get_item(item_id)

            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=item_id,
                name=catalog_item.name if catalog_item else "Item",
                amount=remaining_quantity,
                equipped=False,
                grh_id=catalog_item.graphic_id if catalog_item else item_id,
                item_type=catalog_item.item_type.to_client_type() if catalog_item else 1,
                max_hit=catalog_item.max_damage if catalog_item and catalog_item.max_damage else 0,
                min_hit=catalog_item.min_damage if catalog_item and catalog_item.min_damage else 0,
                max_def=catalog_item.defense if catalog_item and catalog_item.defense else 0,
                min_def=catalog_item.defense if catalog_item and catalog_item.defense else 0,
                sale_price=float(catalog_item.value) if catalog_item else 0.0,
            )

    async def _restore_resource_and_update_stats(
        self,
        user_id: int,
        restore_amount: int,
        current_value: int,
        max_value: int,
        update_func: Callable[[int, int], Awaitable[None]],
        resource_name: str,
    ) -> None:
        """Helper común para restaurar un recurso y actualizar stats.

        Args:
            user_id: ID del usuario.
            restore_amount: Cantidad a restaurar.
            current_value: Valor actual del recurso.
            max_value: Valor máximo del recurso.
            update_func: Función para actualizar el recurso.
            resource_name: Nombre del recurso (para logging).
        """
        # Calcular nuevo valor (no exceder máximo)
        new_value = min(current_value + restore_amount, max_value)

        # Actualizar recurso
        await update_func(user_id, new_value)

        # Obtener stats actualizados para enviar al cliente
        stats = await self.player_repo.get_stats(user_id)
        if stats:
            await self.message_sender.send_update_user_stats(**stats)

        logger.debug(
            "%s restaurado: user_id=%d +%d %s (actual: %d/%d)",
            resource_name,
            user_id,
            restore_amount,
            resource_name,
            new_value,
            max_value,
        )

    async def _handle_hp_potion(self, user_id: int, item_data: dict[str, object]) -> None:
        """Maneja poción de HP (Tipo 3)."""
        if not self.player_repo:
            return

        # Restaurar HP (usar MaxModificador como valor)
        max_mod = item_data.get("MaxModificador", 30)
        restore_amount = int(max_mod) if isinstance(max_mod, (int, str)) else 30

        current_hp = await self.player_repo.get_current_hp(user_id)
        max_hp = await self.player_repo.get_max_hp(user_id)

        await self._restore_resource_and_update_stats(
            user_id=user_id,
            restore_amount=restore_amount,
            current_value=current_hp,
            max_value=max_hp,
            update_func=self.player_repo.update_hp,
            resource_name="HP",
        )

    async def _handle_mana_potion(self, user_id: int, item_data: dict[str, object]) -> None:
        """Maneja poción de Mana (Tipo 4)."""
        if not self.player_repo:
            return

        # Restaurar Mana (usar valor aleatorio entre MinModificador y MaxModificador)
        min_mod_val = item_data.get("MinModificador", 12)
        max_mod_val = item_data.get("MaxModificador", 20)
        min_mod = int(min_mod_val) if isinstance(min_mod_val, (int, str)) else 12
        max_mod = int(max_mod_val) if isinstance(max_mod_val, (int, str)) else 20
        restore_amount = random.randint(min_mod, max_mod)

        min_mana, max_mana = await self.player_repo.get_mana(user_id)

        await self._restore_resource_and_update_stats(
            user_id=user_id,
            restore_amount=restore_amount,
            current_value=min_mana,
            max_value=max_mana,
            update_func=self.player_repo.update_mana,
            resource_name="Mana",
        )

    async def _handle_attribute_potion(
        self,
        user_id: int,
        item_data: dict[str, object],
        attribute_name: str,
        default_min_mod: int,
        default_max_mod: int,
        set_modifier_func: Callable[[int, float, int], Awaitable[None]],
    ) -> None:
        """Maneja pociones de atributos (Agilidad, Fuerza, etc.).

        Args:
            user_id: ID del usuario.
            item_data: Datos del item.
            attribute_name: Nombre del atributo (para logging).
            default_min_mod: Valor mínimo por defecto del modificador.
            default_max_mod: Valor máximo por defecto del modificador.
            set_modifier_func: Función para establecer el modificador en el repositorio.
        """
        if not self.player_repo:
            return

        # Calcular modificador aleatorio
        min_mod_val = item_data.get("MinModificador", default_min_mod)
        max_mod_val = item_data.get("MaxModificador", default_max_mod)
        min_mod = int(min_mod_val) if isinstance(min_mod_val, (int, str)) else default_min_mod
        max_mod = int(max_mod_val) if isinstance(max_mod_val, (int, str)) else default_max_mod
        modifier_value = random.randint(min_mod, max_mod)

        # Duración en segundos (DuracionEfecto está en milisegundos)
        duration_ms_val = item_data.get("DuracionEfecto", 1000)
        duration_ms = int(duration_ms_val) if isinstance(duration_ms_val, (int, str)) else 1000
        duration_seconds = duration_ms / 1000.0
        expires_at = time.time() + duration_seconds

        # Aplicar modificador
        await set_modifier_func(user_id, expires_at, modifier_value)

        # Obtener atributos actualizados y enviar UPDATE
        attributes = await self.player_repo.get_player_attributes(user_id)
        if attributes:
            await self.message_sender.send_update_strength_and_dexterity(
                strength=attributes.strength,
                dexterity=attributes.agility,
            )

        logger.info(
            "%s modificada: user_id=%d +%d hasta %.2f (%.1fs)",
            attribute_name,
            user_id,
            modifier_value,
            expires_at,
            duration_seconds,
        )

    async def _handle_agility_potion(self, user_id: int, item_data: dict[str, object]) -> None:
        """Maneja poción de Agilidad (Tipo 1)."""
        await self._handle_attribute_potion(
            user_id=user_id,
            item_data=item_data,
            attribute_name="Agilidad",
            default_min_mod=3,
            default_max_mod=5,
            set_modifier_func=self.player_repo.set_agility_modifier,
        )

    async def _handle_strength_potion(self, user_id: int, item_data: dict[str, object]) -> None:
        """Maneja poción de Fuerza (Tipo 2)."""
        await self._handle_attribute_potion(
            user_id=user_id,
            item_data=item_data,
            attribute_name="Fuerza",
            default_min_mod=2,
            default_max_mod=6,
            set_modifier_func=self.player_repo.set_strength_modifier,
        )

    async def _handle_cure_poison_potion(self, user_id: int) -> None:
        """Maneja poción de Cura Veneno (Tipo 5)."""
        if not self.player_repo:
            return

        # Remover envenenamiento
        await self.player_repo.update_poisoned_until(user_id, 0.0)
        await self.message_sender.send_console_msg("Te has curado del envenenamiento.")
        logger.info("Veneno curado: user_id=%d", user_id)

    async def _handle_invisibility_potion(self, user_id: int) -> None:
        """Maneja poción de Invisibilidad (Tipo 6)."""
        if not self.player_repo or not self.map_manager or not self.account_repo:
            return

        # Duración por defecto (5 minutos como en el hechizo)
        invisibility_duration_seconds = 300.0
        invisible_until = time.time() + invisibility_duration_seconds

        await self.player_repo.update_invisible_until(user_id, invisible_until)
        logger.info(
            "Invisibilidad aplicada: user_id=%d hasta %.2f (%.1fs)",
            user_id,
            invisible_until,
            invisibility_duration_seconds,
        )

        # Enviar CHARACTER_REMOVE a otros jugadores
        position = await self.player_repo.get_position(user_id)
        if position:
            map_id = position["map"]
            # Broadcast CHARACTER_REMOVE excluyendo al propio jugador
            other_senders = self.map_manager.get_all_message_senders_in_map(
                map_id, exclude_user_id=user_id
            )
            for other_sender in other_senders:
                await other_sender.send_character_remove(user_id)
            logger.info(
                "user_id %d invisible por poción - CHARACTER_REMOVE a %d jugadores",
                user_id,
                len(other_senders),
            )

        await self.message_sender.send_console_msg("Te has vuelto invisible.")
