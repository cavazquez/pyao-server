"""Servicio de lógica de jugador."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.services.player.equipment_service import EquipmentService
from src.repositories.inventory_repository import InventoryRepository
from src.items_catalog import get_item
from src.visual_effects import FXLoops, VisualEffectID

if TYPE_CHECKING:
    from src.repositories.account_repository import AccountRepository
    from src.repositories.equipment_repository import EquipmentRepository
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class PlayerService:
    """Servicio que encapsula la lógica de obtención de datos y envío al cliente."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        message_sender: MessageSender,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Inicializa el servicio de jugador.

        Args:
            player_repo: Repositorio de jugadores.
            message_sender: Enviador de mensajes al cliente.
            account_repo: Repositorio de cuentas (opcional).
        """
        self.player_repo = player_repo
        self.message_sender = message_sender
        self.account_repo = account_repo

    async def send_position(self, user_id: int) -> dict[str, int]:
        """Obtiene posición, crea default si no existe, envía CHANGE_MAP.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con la posición (x, y, map).
        """
        position = await self.player_repo.get_position(user_id)

        if position is None:
            # Crear posición por defecto
            default_x = 50
            default_y = 50
            default_map = 1
            await self.player_repo.set_position(user_id, default_x, default_y, default_map)
            logger.info(
                "Posición inicial creada para user_id %d: (%d, %d) en mapa %d",
                user_id,
                default_x,
                default_y,
                default_map,
            )
            position = {"x": default_x, "y": default_y, "map": default_map}

        # Enviar cambio de mapa
        await self.message_sender.send_change_map(position["map"])
        return position

    async def send_attributes(self, user_id: int) -> dict[str, int]:
        """Obtiene atributos, crea defaults si no existen, NO los envía (on-demand).

        Los atributos se envían solo cuando el cliente los solicita con /EST.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con los atributos.
        """
        attributes = await self.player_repo.get_attributes(user_id)

        if attributes is None:
            # Crear atributos por defecto
            attributes = {
                "strength": 10,
                "agility": 10,
                "intelligence": 10,
                "charisma": 10,
                "constitution": 10,
            }
            await self.player_repo.set_attributes(user_id=user_id, **attributes)
            logger.info("Atributos por defecto creados en Redis para user_id %d", user_id)

        return attributes

    async def send_stats(self, user_id: int) -> dict[str, int]:
        """Obtiene stats, crea defaults si no existen, envía UPDATE_USER_STATS.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con las estadísticas.
        """
        user_stats = await self.player_repo.get_stats(user_id)

        if user_stats is None:
            # Crear stats por defecto
            user_stats = {
                "max_hp": 100,
                "min_hp": 100,
                "max_mana": 100,
                "min_mana": 50,  # Empezar con 50% de mana para testing
                "max_sta": 100,
                "min_sta": 100,
                "gold": 0,
                "level": 1,
                "elu": 300,
                "experience": 0,
            }
            await self.player_repo.set_stats(user_id=user_id, **user_stats)
            logger.info("Estadísticas por defecto creadas en Redis para user_id %d", user_id)

        # Enviar stats al cliente
        await self.message_sender.send_update_user_stats(**user_stats)
        return user_stats

    async def send_hunger_thirst(self, user_id: int) -> dict[str, int]:
        """Obtiene hambre/sed, crea defaults si no existen, envía UPDATE_HUNGER_AND_THIRST.

        Args:
            user_id: ID del usuario.

        Returns:
            Diccionario con hambre y sed.
        """
        hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)

        if hunger_thirst is None:
            # Crear valores por defecto
            await self.player_repo.set_hunger_thirst(
                user_id=user_id,
                max_water=100,
                min_water=100,
                max_hunger=100,
                min_hunger=100,
                thirst_flag=0,
                hunger_flag=0,
                water_counter=0,
                hunger_counter=0,
            )
            logger.info("Hambre y sed por defecto creadas en Redis para user_id %d", user_id)
            hunger_thirst = await self.player_repo.get_hunger_thirst(user_id)

        # Enviar hambre y sed al cliente
        if hunger_thirst:
            await self.message_sender.send_update_hunger_and_thirst(
                max_water=hunger_thirst["max_water"],
                min_water=hunger_thirst["min_water"],
                max_hunger=hunger_thirst["max_hunger"],
                min_hunger=hunger_thirst["min_hunger"],
            )

        return hunger_thirst or {}

    async def spawn_character(
        self,
        user_id: int,
        username: str,
        position: dict[str, int],
    ) -> None:
        """Envía CHARACTER_CREATE del personaje.

        Args:
            user_id: ID del usuario.
            username: Nombre del usuario.
            position: Posición del personaje (x, y, map).
        """
        # Obtener body y head desde Redis
        char_body = 1  # Valor por defecto
        char_head = 1  # Valor por defecto

        if self.account_repo:
            account_data = await self.account_repo.get_account(username)
            if account_data:
                char_body = int(account_data.get("char_race", 1))
                char_head = int(account_data.get("char_head", 1))
                # Si body es 0, usar valor por defecto
                if char_body == 0:
                    char_body = 1

        char_heading = position.get("heading", 3)  # Obtener heading de Redis, default Sur

        # Enviar CHARACTER_CREATE con efecto de spawn
        await self.message_sender.send_character_create(
            char_index=user_id,
            body=char_body,
            head=char_head,
            heading=char_heading,
            x=position["x"],
            y=position["y"],
            fx=VisualEffectID.SPAWN_YELLOW,  # Efecto amarillo de aparición
            loops=FXLoops.ONCE,  # Reproducir una vez
            name=username,
        )

        logger.info("Personaje spawneado para user_id %d", user_id)

    async def send_inventory(
        self, user_id: int, equipment_repo: EquipmentRepository | None = None
    ) -> None:
        """Obtiene inventario y envía solo slots con items al cliente.

        Args:
            user_id: ID del usuario.
            equipment_repo: Repositorio de equipamiento (opcional).
        """
        inventory_repo = InventoryRepository(self.player_repo.redis)
        inventory = await inventory_repo.get_inventory(user_id)

        # Obtener items equipados si el repositorio está disponible
        equipped_slots = {}
        if equipment_repo:
            equipment_service = EquipmentService(equipment_repo, inventory_repo)
            equipped_slots = await equipment_service.get_equipped_items(user_id)

        # Contar items no vacíos
        non_empty_slots = sum(1 for v in inventory.values() if v and isinstance(v, str))
        logger.info("Enviando inventario para user_id %d (%d items)", user_id, non_empty_slots)

        for i in range(1, InventoryRepository.MAX_SLOTS + 1):
            slot_key = f"slot_{i}"
            slot_value = inventory.get(slot_key, "")

            # Solo enviar slots con items (no enviar vacíos)
            if slot_value and isinstance(slot_value, str):
                try:
                    item_id, quantity = slot_value.split(":")
                    item = get_item(int(item_id))

                    if item:
                        is_equipped = i in equipped_slots
                        equipped_str = " [EQUIPADO]" if is_equipped else ""
                        logger.info(
                            "Item enviado: Slot %d -> '%s' (ID=%d, Cantidad=%s, Tipo=%s)%s",
                            i,
                            item.name,
                            item.item_id,
                            quantity,
                            item.item_type.name,
                            equipped_str,
                        )
                        await self.message_sender.send_change_inventory_slot(
                            slot=i,
                            item_id=item.item_id,
                            name=item.name,
                            amount=int(quantity),
                            equipped=is_equipped,
                            grh_id=item.graphic_id,
                            item_type=item.item_type.to_client_type(),
                            max_hit=item.max_damage or 0,
                            min_hit=item.min_damage or 0,
                            max_def=item.defense or 0,
                            min_def=item.defense or 0,
                            sale_price=float(item.value),
                        )
                    else:
                        logger.warning("Item %s no encontrado en catálogo", item_id)
                except (ValueError, AttributeError) as e:
                    logger.warning("Error procesando slot %d: %s", i, e)
