"""Handler para comando de usar item."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.use_item_command import UseItemCommand
from src.models.item_constants import BOAT_ITEM_ID
from src.models.items_catalog import get_item
from src.repositories.equipment_repository import EquipmentRepository
from src.repositories.inventory_repository import InventoryRepository

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

logger = logging.getLogger(__name__)

WORK_TOOL_SKILLS: dict[int, int] = {
    561: 9,  # Hacha de Leñador → Skill Talar
    562: 13,  # Piquete de Minero → Skill Minería
    563: 12,  # Caña de pescar → Skill Pesca
}

HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4


class UseItemCommandHandler(CommandHandler):
    """Handler para comando de usar item (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_resources: MapResourcesService | None,
        account_repo: AccountRepository | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_resources: Servicio de recursos de mapa.
            account_repo: Repositorio de cuentas.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_resources = map_resources
        self.account_repo = account_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de usar item (solo lógica de negocio).

        Args:
            command: Comando de usar item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, UseItemCommand):
            return CommandResult.error("Comando inválido: se esperaba UseItemCommand")

        user_id = command.user_id
        slot = command.slot
        username = command.username

        logger.debug(
            "UseItemCommandHandler: Procesando uso de item user_id=%d slot=%d", user_id, slot
        )

        # Validar dependencias
        if not self.player_repo:
            logger.error("PlayerRepository no está disponible para usar item")
            return CommandResult.error("Error interno: repositorio no disponible")

        inventory_repo = InventoryRepository(self.player_repo.redis)
        slot_data = await inventory_repo.get_slot(user_id, slot)

        if not slot_data:
            logger.warning("Slot %d vacío", slot)
            return CommandResult.error("El slot está vacío")

        item_id, quantity = slot_data

        # Herramientas de trabajo: activar modo trabajo si están equipadas
        if item_id in WORK_TOOL_SKILLS:
            return await self._handle_work_tool(user_id, item_id, slot)

        # Barca: alternar modo navegación
        if item_id == BOAT_ITEM_ID:
            return await self._handle_boat(user_id, slot, username)

        # Caso especial para manzanas (ID 1)
        if item_id == 1:
            return await self._handle_apple_consumption(
                user_id, item_id, quantity, slot, inventory_repo
            )

        # Si llegamos aquí, el ítem no tiene un comportamiento definido
        logger.info("El ítem %d no tiene un comportamiento de uso definido", item_id)
        return CommandResult.ok(data={"item_id": item_id, "handled": False})

    async def _handle_work_tool(self, user_id: int, item_id: int, slot: int) -> CommandResult:
        """Maneja el uso de herramientas de trabajo.

        Returns:
            Resultado de la ejecución.
        """
        if not self.player_repo:
            return CommandResult.error("Error interno: repositorio no disponible")

        equipment_repo = EquipmentRepository(self.player_repo.redis)
        equipped_slot = await equipment_repo.is_slot_equipped(user_id, slot)

        if equipped_slot is None:
            await self.message_sender.send_console_msg(
                "Debes tener equipada la herramienta para trabajar."
            )
            logger.info(
                "user_id %d intentó usar herramienta %d sin tenerla equipada",
                user_id,
                item_id,
            )
            return CommandResult.error("Debes tener equipada la herramienta para trabajar.")

        skill_type = WORK_TOOL_SKILLS[item_id]
        await self.message_sender.send_work_request_target(skill_type)
        logger.info(
            "user_id %d activó modo trabajo (skill=%d) con item %d en slot %d",
            user_id,
            skill_type,
            item_id,
            slot,
        )
        return CommandResult.ok(
            data={"item_id": item_id, "skill_type": skill_type, "handled": True}
        )

    async def _handle_boat(
        self,
        user_id: int,
        slot: int,  # noqa: ARG002
        username: str | None,
    ) -> CommandResult:
        """Maneja el uso de la barca.

        Args:
            user_id: ID del jugador.
            slot: Slot del inventario (no usado, pero necesario para consistencia).
            username: Username del jugador (opcional, para actualización visual).

        Returns:
            Resultado de la ejecución.
        """
        if not self.player_repo:
            return CommandResult.error("Error interno: repositorio no disponible")

        is_sailing = await self.player_repo.is_sailing(user_id)

        # Si vamos a entrar en modo navegación y tenemos MapResourcesService,
        # exigir estar cerca del agua (en un radio de 1 tile alrededor).
        if not is_sailing and self.map_resources and not await self._can_start_sailing(user_id):
            return CommandResult.error("Debes estar cerca del agua para comenzar a navegar.")

        # Si vamos a salir de navegación y tenemos MapResourcesService,
        # exigir estar cerca de tierra:
        # - ya sea en el radio 1 (3x3 alrededor)
        # - o bien a distancia 1-2 en la dirección actual del jugador.
        if is_sailing and self.map_resources and not await self._can_stop_sailing(user_id):
            return CommandResult.error(
                "No puedes dejar de navegar en medio del agua. Busca la costa."
            )

        await self.player_repo.set_sailing(user_id, not is_sailing)
        await self.message_sender.send_console_msg(
            "Has cambiado al modo de navegación"
            if not is_sailing
            else "Has cambiado al modo de caminata"
        )
        # Informar al cliente para que alterne su modo de navegación
        await self.message_sender.send_navigate_toggle()

        # Cambiar visualmente el cuerpo a barco al entrar en navegación
        # y restaurar el body original al salir.
        await self._update_character_visual(user_id, is_sailing, username)

        logger.info(
            "user_id %d cambió al modo de navegación"
            if not is_sailing
            else "user_id %d cambió al modo de caminata",
            user_id,
        )
        return CommandResult.ok(
            data={"item_id": BOAT_ITEM_ID, "is_sailing": not is_sailing, "handled": True}
        )

    async def _update_character_visual(
        self, user_id: int, was_sailing: bool, username: str | None
    ) -> None:
        """Actualiza la apariencia visual del personaje al cambiar modo navegación."""
        if not self.account_repo or not username:
            return

        account_data = await self.account_repo.get_account(username)
        if not account_data:
            return

        original_body = int(account_data.get("char_race", 1)) or 1
        original_head = int(account_data.get("char_head", 1)) or 1

        # Elegir un body de barco compatible con el cliente (ShipIds en Godot)
        ship_body_id = 84

        # Obtener heading actual desde Redis para no desincronizar
        position = await self.player_repo.get_position(user_id)
        heading = position.get("heading", 3) if position else 3

        # Entrar en navegación: usar body de barco y sin cabeza (head=0).
        # Salir de navegación: restaurar body y head originales.
        if not was_sailing:
            new_body = ship_body_id
            new_head = 0
        else:
            new_body = original_body
            new_head = original_head

        await self.message_sender.send_character_change(
            char_index=user_id,
            body=new_body,
            head=new_head,
            heading=heading,
        )

    async def _can_start_sailing(self, user_id: int) -> bool:
        """Valida que el jugador esté lo suficientemente cerca del agua para navegar.

        Returns:
            True si el jugador puede comenzar a navegar, False en caso contrario.
        """
        position = await self.player_repo.get_position(user_id) if self.player_repo else None
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d para barca", user_id)
            return False

        map_id = position.get("map")
        x = position.get("x")
        y = position.get("y")
        if not (
            isinstance(map_id, int)
            and isinstance(x, int)
            and isinstance(y, int)
            and self.map_resources
        ):
            return False

        near_water = False
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if self.map_resources.has_water(map_id, x + dx, y + dy):
                    near_water = True
                    break
            if near_water:
                break

        if not near_water:
            await self.message_sender.send_console_msg(
                "Debes estar cerca del agua para comenzar a navegar."
            )
            return False

        return True

    async def _can_stop_sailing(self, user_id: int) -> bool:
        """Valida que el jugador esté lo suficientemente cerca de tierra para dejar de navegar.

        Returns:
            True si el jugador puede dejar de navegar, False en caso contrario.
        """
        position = await self.player_repo.get_position(user_id) if self.player_repo else None
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d para barca", user_id)
            return False

        map_id = position.get("map")
        x = position.get("x")
        y = position.get("y")
        heading = position.get("heading")
        if not (
            isinstance(map_id, int)
            and isinstance(x, int)
            and isinstance(y, int)
            and self.map_resources
        ):
            return False

        near_land = False

        # 1) Tierra en el radio 1 alrededor
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if not self.map_resources.has_water(map_id, x + dx, y + dy):
                    near_land = True
                    break
            if near_land:
                break

        # 2) Tierra a distancia 1-2 en la dirección actual
        if not near_land and isinstance(heading, int):
            # Tile 1 adelante
            tx1, ty1 = x, y
            if heading == HEADING_NORTH:
                ty1 -= 1
            elif heading == HEADING_EAST:
                tx1 += 1
            elif heading == HEADING_SOUTH:
                ty1 += 1
            elif heading == HEADING_WEST:
                tx1 -= 1

            # Tile 2 adelante
            tx2, ty2 = tx1, ty1
            if heading == HEADING_NORTH:
                ty2 -= 1
            elif heading == HEADING_EAST:
                tx2 += 1
            elif heading == HEADING_SOUTH:
                ty2 += 1
            elif heading == HEADING_WEST:
                tx2 -= 1

            if not self.map_resources.has_water(
                map_id, tx1, ty1
            ) or not self.map_resources.has_water(map_id, tx2, ty2):
                near_land = True

        if not near_land:
            await self.message_sender.send_console_msg(
                "No puedes dejar de navegar en medio del agua. Busca la costa."
            )
            return False

        return True

    async def _handle_apple_consumption(
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
