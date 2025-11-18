"""Tarea para manejar el uso de ítems del inventario."""

import logging
from typing import TYPE_CHECKING

from src.models.item_constants import BOAT_ITEM_ID
from src.models.items_catalog import get_item
from src.network.session_manager import SessionManager
from src.repositories.equipment_repository import EquipmentRepository
from src.repositories.inventory_repository import InventoryRepository
from src.tasks.task import Task

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


class TaskUseItem(Task):
    """Maneja el uso de un ítem del inventario."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        slot: int,
        player_repo: PlayerRepository | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        map_resources: MapResourcesService | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Initialize a TaskUseItem instance with dependencies and context.

        Args:
            data: Packet payload associated with the USE_ITEM request.
            message_sender: Facade used to communicate responses to the client.
            slot: Inventory slot requested by the client.
            player_repo: Repository for accessing player data. Optional.
            session_data: Session context dictionary keyed by user-related data. Optional.
            map_resources: Service for querying map resources such as water tiles.
            account_repo: Repository for accessing account data, used for visual changes
                when toggling navigation. Optional.
        """
        super().__init__(data, message_sender)
        self.slot = slot
        self.player_repo = player_repo
        self.session_data = session_data or {}
        self.map_resources = map_resources
        self.account_repo = account_repo

    async def execute(self) -> None:
        """Ejecuta el uso de un ítem del inventario."""
        # TODO: Implementar sistema completo de ítems con comportamientos
        # Actualmente solo maneja manzanas como caso especial

        if not self.session_data or not self.player_repo:
            logger.warning("Datos de sesión o repositorio no disponibles")
            return

        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de usar ítem sin estar logueado")
            return

        inventory_repo = InventoryRepository(self.player_repo.redis)
        slot_data = await inventory_repo.get_slot(user_id, self.slot)

        if not slot_data:
            logger.warning("Slot %d vacío", self.slot)
            return

        item_id, quantity = slot_data

        # Herramientas de trabajo: activar modo trabajo si están equipadas
        if item_id in WORK_TOOL_SKILLS:
            await self._handle_work_tool(user_id, item_id)
            return

        # Barca: alternar modo navegación
        if item_id == BOAT_ITEM_ID:
            await self._handle_boat(user_id)
            return

        # Caso especial para manzanas (ID 1)
        if item_id == 1:
            await self._handle_apple_consumption(user_id, item_id, quantity, inventory_repo)
            return

        # Si llegamos aquí, el ítem no tiene un comportamiento definido
        logger.info("El ítem %d no tiene un comportamiento de uso definido", item_id)

    async def _handle_work_tool(self, user_id: int, item_id: int) -> None:
        """Maneja el uso de herramientas de trabajo."""
        if not self.player_repo:
            return

        equipment_repo = EquipmentRepository(self.player_repo.redis)
        equipped_slot = await equipment_repo.is_slot_equipped(user_id, self.slot)

        if equipped_slot is None:
            await self.message_sender.send_console_msg(
                "Debes tener equipada la herramienta para trabajar."
            )
            logger.info(
                "user_id %d intentó usar herramienta %d sin tenerla equipada",
                user_id,
                item_id,
            )
            return

        skill_type = WORK_TOOL_SKILLS[item_id]
        await self.message_sender.send_work_request_target(skill_type)
        logger.info(
            "user_id %d activó modo trabajo (skill=%d) con item %d en slot %d",
            user_id,
            skill_type,
            item_id,
            self.slot,
        )

    async def _handle_boat(self, user_id: int) -> None:
        """Maneja el uso de la barca."""
        if not self.player_repo:
            return

        is_sailing = await self.player_repo.is_sailing(user_id)

        # Si vamos a entrar en modo navegación y tenemos MapResourcesService,
        # exigir estar cerca del agua (en un radio de 1 tile alrededor).
        if not is_sailing and self.map_resources and not await self._can_start_sailing(user_id):
            return

        # Si vamos a salir de navegación y tenemos MapResourcesService,
        # exigir estar cerca de tierra:
        # - ya sea en el radio 1 (3x3 alrededor)
        # - o bien a distancia 1-2 en la dirección actual del jugador.
        if is_sailing and self.map_resources and not await self._can_stop_sailing(user_id):
            return
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
        if self.account_repo and "username" in self.session_data:
            username = self.session_data["username"]
            if isinstance(username, str):
                account_data = await self.account_repo.get_account(username)
            else:
                account_data = None
        else:
            account_data = None

        if account_data:
            original_body = int(account_data.get("char_race", 1)) or 1
            original_head = int(account_data.get("char_head", 1)) or 1

            # Elegir un body de barco compatible con el cliente (ShipIds en Godot)
            ship_body_id = 84

            # Obtener heading actual desde Redis para no desincronizar
            position = await self.player_repo.get_position(user_id)
            heading = position.get("heading", 3) if position else 3

            # Entrar en navegación: usar body de barco y sin cabeza (head=0).
            # Salir de navegación: restaurar body y head originales.
            if not is_sailing:
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
        logger.info(
            "user_id %d cambió al modo de navegación"
            if not is_sailing
            else "user_id %d cambió al modo de caminata",
            user_id,
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
        self, user_id: int, item_id: int, quantity: int, inventory_repo: InventoryRepository
    ) -> None:
        """Maneja el consumo de manzanas."""
        logger.info("Consumiendo manzana del slot %d", self.slot)

        # Consumir una manzana utilizando la API del repositorio
        if quantity <= 1:
            await inventory_repo.clear_slot(user_id, self.slot)
        else:
            removed = await inventory_repo.remove_item(user_id, self.slot, 1)
            if not removed:
                logger.warning(
                    "No se pudo decrementar la cantidad del slot %d para el ítem %d",
                    self.slot,
                    item_id,
                )
                return

        # Restaurar hambre utilizando la API de hambre/sed
        await self._restore_hunger(user_id)

        await self.message_sender.send_console_msg("¡Has comido una manzana!")

        # Actualizar el slot en el cliente
        await self._update_inventory_slot_after_consumption(user_id, item_id, inventory_repo)

    async def _restore_hunger(self, user_id: int) -> None:
        """Restaura el hambre del jugador."""
        if not self.player_repo:
            return

        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)
        if not hunger_thirst:
            logger.warning("No se encontraron datos de hambre/sed para user_id %d", user_id)
            await self.message_sender.send_console_msg("No se pudo restaurar el hambre.")
            return

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

    async def _update_inventory_slot_after_consumption(
        self, user_id: int, item_id: int, inventory_repo: InventoryRepository
    ) -> None:
        """Actualiza el slot del inventario después de consumir un ítem."""
        updated_slot = await inventory_repo.get_slot(user_id, self.slot)

        if not updated_slot:
            await self.message_sender.send_change_inventory_slot(
                slot=self.slot,
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
                slot=self.slot,
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
