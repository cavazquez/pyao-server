"""Tarea para doble click (items del inventario o NPCs)."""

import logging
from typing import TYPE_CHECKING

from src.models.items_catalog import get_item
from src.network.packet_data import DoubleClickData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.repositories.inventory_repository import InventoryRepository
from src.tasks.task import Task
from src.utils.packet_length_validator import PacketLengthValidator

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Constante para diferenciar entre slots de inventario y CharIndex de NPCs
MAX_INVENTORY_SLOT = 100


class TaskDoubleClick(Task):
    """Maneja doble click en items del inventario o NPCs."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        inventory_repo: InventoryRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de doble click.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            inventory_repo: Repositorio de inventario (inyectable para tests o cache).
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.inventory_repo = inventory_repo
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta doble click (item o NPC)."""
        # Validar longitud del packet usando PacketLengthValidator
        if not await PacketLengthValidator.validate_min_length(self.data, 3, self.message_sender):
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de doble click sin estar logueado")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        target = validator.read_slot(min_slot=0, max_slot=255)  # Puede ser slot, CharIndex o mapa

        if validator.has_errors() or target is None:
            error_msg = (
                validator.get_error_message() if validator.has_errors() else "Target inválido"
            )
            await self.message_sender.send_console_msg(error_msg)
            return

        # Crear dataclass con datos validados
        click_data = DoubleClickData(target=target)

        # Doble click en el mapa envía coordenadas adicionales (x, y)
        if reader.has_more_data():
            remaining_coords: list[int] = []
            while reader.has_more_data():
                remaining_coords.append(reader.read_byte())

            logger.debug(
                "Doble click sobre el mapa detectado: coords=%s, se ignora.",
                [click_data.target, *remaining_coords],
            )
            return

        if click_data.target == 0:
            logger.debug("Doble click sobre el mapa (target=0), se ignora.")
            return

        try:
            # Si el target es > MAX_INVENTORY_SLOT, probablemente es un CharIndex de NPC
            # Los slots de inventario van de 1-20 típicamente
            if click_data.target > MAX_INVENTORY_SLOT:
                await self._handle_npc_double_click(user_id, click_data.target)
            else:
                await self._handle_item_use(user_id, click_data.target)

        except Exception:
            logger.exception("Error procesando DOUBLE_CLICK")

    async def _handle_item_use(self, user_id: int, slot: int) -> None:
        """Maneja el uso de un item del inventario.

        Args:
            user_id: ID del usuario.
            slot: Slot del inventario.
        """
        # Verificar que tengamos player_repo
        if not self.player_repo:
            logger.error("player_repo no disponible")
            return

        logger.info("user_id %d intenta usar item en slot %d", user_id, slot)

        inventory_repo = self.inventory_repo
        if not inventory_repo:
            player_redis = getattr(self.player_repo, "redis", None)
            if not player_redis:
                logger.error("inventory_repo no disponible")
                return
            inventory_repo = InventoryRepository(player_redis)
            self.inventory_repo = inventory_repo

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
        removed = await inventory_repo.remove_item(user_id, slot, 1)

        if not removed:
            logger.warning("No se pudo consumir el item en slot %d para user_id %d", slot, user_id)
            return

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

    async def _handle_npc_double_click(self, user_id: int, char_index: int) -> None:
        """Maneja doble click en un NPC.

        Args:
            user_id: ID del usuario.
            char_index: CharIndex del NPC.
        """
        if not self.map_manager or not self.player_repo:
            logger.error("Dependencias no disponibles para interacción con NPC")
            return

        # Obtener posición del jugador para saber en qué mapa está
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return

        map_id = position["map"]

        # Buscar el NPC en el mapa
        npc = self.map_manager.get_npc_by_char_index(map_id, char_index)
        if not npc:
            logger.warning(
                "user_id %d intentó interactuar con NPC inexistente (CharIndex: %d)",
                user_id,
                char_index,
            )
            await self.message_sender.send_console_msg("No hay nadie ahí.")
            return

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
