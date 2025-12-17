"""Handler para comando de doble click (items del inventario o NPCs)."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.double_click_command import DoubleClickCommand
from src.models.items_catalog import get_item
from src.repositories.inventory_repository import InventoryRepository

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constante para diferenciar entre slots de inventario y CharIndex de NPCs
MAX_INVENTORY_SLOT = 100


class DoubleClickCommandHandler(CommandHandler):
    """Handler para comando de doble click (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de doble click (solo lógica de negocio).

        Args:
            command: Comando de doble click.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, DoubleClickCommand):
            return CommandResult.error("Comando inválido: se esperaba DoubleClickCommand")

        user_id = command.user_id
        target = command.target

        logger.info(
            "DoubleClickCommandHandler: user_id=%d hace doble click en target=%d",
            user_id,
            target,
        )

        try:
            # Si el target es > MAX_INVENTORY_SLOT, probablemente es un CharIndex de NPC
            if command.is_npc_click():
                return await self._handle_npc_double_click(user_id, target, command.map_id)
            return await self._handle_item_use(user_id, target)

        except Exception as e:
            logger.exception("Error procesando DOUBLE_CLICK")
            return CommandResult.error(f"Error al procesar doble click: {e!s}")

    async def _handle_item_use(self, user_id: int, slot: int) -> CommandResult:
        """Maneja el uso de un item del inventario.

        Args:
            user_id: ID del usuario.
            slot: Slot del inventario.

        Returns:
            Resultado de la ejecución.
        """
        logger.info("user_id %d intenta usar item en slot %d", user_id, slot)

        # Crear inventory_repo desde player_repo.redis
        player_redis = getattr(self.player_repo, "redis", None)
        if not player_redis:
            logger.error("inventory_repo no disponible")
            return CommandResult.error("Error interno: repositorio no disponible")

        inventory_repo = InventoryRepository(player_redis)
        slot_data = await inventory_repo.get_slot(user_id, slot)

        if not slot_data:
            await self.message_sender.send_console_msg("El slot está vacío.")
            return CommandResult.error("El slot está vacío")

        item_id, _quantity = slot_data

        # Obtener el item del catálogo
        item = get_item(item_id)
        if not item:
            logger.error("Item %d no encontrado en catálogo", item_id)
            await self.message_sender.send_console_msg("Item no válido.")
            return CommandResult.error("Item no válido")

        # Verificar si el item se puede usar
        if not item.can_use():
            await self.message_sender.send_console_msg(f"No puedes usar {item.name}.")
            return CommandResult.error(f"No puedes usar {item.name}")

        # Usar el item
        if item.consumable:
            return await self._use_consumable(user_id, slot, item, inventory_repo)
        if item.equippable:
            await self.message_sender.send_console_msg(
                f"Equipar items aún no está implementado. Item: {item.name}"
            )
            return CommandResult.error("Equipar items aún no está implementado")

        return CommandResult.error("Item no se puede usar")

    async def _use_consumable(  # type: ignore[no-untyped-def]
        self,
        user_id: int,
        slot: int,
        item,  # noqa: ANN001 - Item from items_catalog
        inventory_repo: InventoryRepository,
    ) -> CommandResult:
        """Usa un item consumible.

        Args:
            user_id: ID del jugador.
            slot: Slot del item.
            item: Item a usar.
            inventory_repo: Repositorio de inventario.

        Returns:
            Resultado de la ejecución.
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
            return CommandResult.error("No se pudo consumir el item")

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

        return CommandResult.ok(
            data={
                "item_id": item.item_id,
                "item_name": item.name,
                "slot": slot,
                "effects": effects_applied,
            }
        )

    async def _handle_npc_double_click(
        self, user_id: int, char_index: int, map_id: int | None
    ) -> CommandResult:
        """Maneja doble click en un NPC.

        Args:
            user_id: ID del usuario.
            char_index: CharIndex del NPC.
            map_id: ID del mapa donde está el jugador.

        Returns:
            Resultado de la ejecución.
        """
        if not self.map_manager:
            logger.error("MapManager no disponible para interacción con NPC")
            return CommandResult.error("Error interno: gestor de mapas no disponible")

        if not map_id:
            logger.error("map_id no disponible para interacción con NPC")
            return CommandResult.error("Error interno: mapa no disponible")

        # Buscar el NPC en el mapa
        npc = self.map_manager.get_npc_by_char_index(map_id, char_index)
        if not npc:
            logger.warning(
                "user_id %d intentó interactuar con NPC inexistente (CharIndex: %d)",
                user_id,
                char_index,
            )
            await self.message_sender.send_console_msg("No hay nadie ahí.")
            return CommandResult.error("No hay nadie ahí")

        # Interactuar según el tipo de NPC
        if npc.is_hostile:
            # NPC hostil - preparar para combate
            await self.message_sender.send_console_msg(
                f"{npc.name} te mira con hostilidad. Sistema de combate en desarrollo."
            )
        else:
            # NPC amigable - mostrar diálogo
            await self.message_sender.send_console_msg(
                f"{npc.name}: {npc.description or 'Hola, aventurero.'}"
            )

        logger.info(
            "user_id %d interactuó con NPC %s (CharIndex: %d)",
            user_id,
            npc.name,
            char_index,
        )

        return CommandResult.ok(
            data={
                "npc_name": npc.name,
                "char_index": char_index,
                "is_hostile": npc.is_hostile,
            }
        )
