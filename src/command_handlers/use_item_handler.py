"""Handler para comando de usar item."""

import logging
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from src.command_handlers.use_item_consumable_handler import UseItemConsumableHandler
from src.command_handlers.use_item_special_handler import UseItemSpecialHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.use_item_command import UseItemCommand
from src.models.item_constants import BOAT_ITEM_ID
from src.models.item_types import ObjType
from src.repositories.inventory_repository import InventoryRepository
from src.services.inventory_notifications import notify_inventory
from src.services.nutrition import NutritionRule, consume_nutrition
from src.services.scroll_learning import ScrollRule, learn_scroll

BOAT_TYPE = 31


if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.multiplayer_broadcast_service import (
        MultiplayerBroadcastService,
    )
    from src.services.skill_action_service import SkillActionService

logger = logging.getLogger(__name__)

WORK_TOOL_SKILLS: dict[int, int] = {
    127: 9,
    187: 13,
    138: 12,
    561: 9,  # Hacha de Leñador → Skill Talar
    562: 13,  # Piquete de Minero → Skill Minería
    563: 12,  # Caña de pescar → Skill Pesca
}


class UseItemCommandHandler(CommandHandler):
    """Handler para comando de usar item (solo lógica de negocio).

    Este handler delega a handlers especializados según el tipo de item:
    - UseItemConsumableHandler: Para pociones y comida
    - UseItemSpecialHandler: Para barca y herramientas de trabajo
    """

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_resources: MapResourcesService | None,
        account_repo: AccountRepository | None,
        message_sender: MessageSender,
        item_catalog: ItemCatalog | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        map_manager: MapManager | None = None,
        skill_actions: SkillActionService | None = None,
        spell_catalog: SpellCatalog | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_resources: Servicio de recursos de mapa.
            account_repo: Repositorio de cuentas.
            skill_actions: Servicio compartido de acciones de habilidades.
            message_sender: Enviador de mensajes.
            item_catalog: Catálogo de items (para datos completos de pociones).
            broadcast_service: Servicio de broadcast multijugador (para invisibilidad).
            map_manager: Gestor de mapas (para obtener message senders).
            spell_catalog: Catálogo autoritativo para validar pergaminos.
        """
        self.spell_catalog = spell_catalog
        self.player_repo = player_repo
        self.map_resources = map_resources
        self.account_repo = account_repo
        self.message_sender = message_sender
        self.skill_actions = skill_actions
        self.item_catalog = item_catalog
        self.broadcast_service = broadcast_service
        self.map_manager = map_manager

        # Inicializar handlers especializados
        self.consumable_handler = UseItemConsumableHandler(
            player_repo=player_repo,
            message_sender=message_sender,
            item_catalog=item_catalog,
            broadcast_service=broadcast_service,
            map_manager=map_manager,
            account_repo=account_repo,
        )

        self.special_handler = UseItemSpecialHandler(
            player_repo=player_repo,
            map_resources=map_resources,
            account_repo=account_repo,
            message_sender=message_sender,
        )

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

        # Herramientas de trabajo: delegar a handler especializado
        if item_id in WORK_TOOL_SKILLS:
            return await self.special_handler.handle_work_tool(user_id, item_id, slot)

        # Barca: delegar a handler especializado
        if (
            self.skill_actions is not None
            and self.item_catalog is not None
            and (self.item_catalog.get_item_data(item_id) or {}).get("ObjType") == BOAT_TYPE
        ):
            result = await self.skill_actions.execute(
                user_id, "navigate", {"slot": slot}, self.message_sender
            )
            return (
                CommandResult.ok(result)
                if result["applied"]
                else CommandResult.error(str(result.get("message", "Navegación rechazada")))
            )
        if item_id == BOAT_ITEM_ID:
            return await self.special_handler.handle_boat(user_id, slot, username)

        if self.item_catalog:
            item_data = self.item_catalog.get_item_data(item_id)
            if item_data and item_data.get("ObjType") in {
                ObjType.COMIDA,
                ObjType.BEBIDA,
                ObjType.BOTELLAS_LLENAS,
            }:
                return await self._consume_nutrition(command, item_id, item_data, inventory_repo)

        # Adaptador para servicios de diagnóstico sin un catálogo concreto.
        if item_id == 1:
            return await self.consumable_handler.handle_apple(
                user_id, item_id, quantity, slot, inventory_repo
            )

        # Detectar si es una poción: delegar a handler de consumibles
        if self.item_catalog:
            item_data = self.item_catalog.get_item_data(item_id)
            if item_data:
                obj_type = item_data.get("ObjType")
                if obj_type == ObjType.PERGAMINOS:
                    return await self._learn_scroll(command, item_id, item_data, inventory_repo)
                if isinstance(obj_type, int) and obj_type == ObjType.POCIONES:
                    potion_type = item_data.get("TipoPocion")
                    if isinstance(potion_type, int):
                        return await self.consumable_handler.handle_potion(
                            user_id,
                            item_id,
                            quantity,
                            slot,
                            inventory_repo,
                            item_data,
                            potion_type,
                        )

        # Si llegamos aquí, el ítem no tiene un comportamiento definido
        logger.info("El ítem %d no tiene un comportamiento de uso definido", item_id)
        return CommandResult.ok(data={"item_id": item_id, "handled": False})

    async def _consume_nutrition(
        self,
        command: UseItemCommand,
        item_id: int,
        item_data: dict[str, object],
        inventory_repo: InventoryRepository,
    ) -> CommandResult:
        """Publica únicamente el consumo y los efectos ya confirmados por Redis.

        Returns:
            Consumo real del catálogo o rechazo sin pérdida del objeto.
        """
        rule = NutritionRule.from_item(item_id, item_data)
        result = await consume_nutrition(
            self.player_repo.redis.redis,
            command.user_id,
            command.slot,
            command.operation_id,
            rule,
            int(inventory_repo.MAX_SLOTS),
            inventory_repo.stacking.max_stack,
        )
        if not result["applied"]:
            return CommandResult.error(result["message"])
        await notify_inventory(self.message_sender, inventory_repo, command.user_id)
        needs = await self.player_repo.get_hunger_thirst(command.user_id) or {}
        await self.message_sender.send_update_hunger_and_thirst(
            max_water=needs.get("max_water", 100),
            min_water=needs.get("min_water", 0),
            max_hunger=needs.get("max_hunger", 100),
            min_hunger=needs.get("min_hunger", 0),
        )
        await self.message_sender.send_update_user_stats_from_repo(
            command.user_id, self.player_repo
        )
        verb = "comido" if item_data["ObjType"] == ObjType.COMIDA else "bebido"
        label = "una manzana" if item_id == 1 else str(item_data["Name"])
        await self.message_sender.send_console_msg(f"¡Has {verb} {label}!")
        return CommandResult.ok({**result, "handled": True})

    async def _learn_scroll(
        self,
        command: UseItemCommand,
        item_id: int,
        item_data: dict[str, object],
        inventory_repo: InventoryRepository,
    ) -> CommandResult:
        """Publica únicamente inventario/libro confirmados, conservando el ID al reintentar.

        Returns:
            Resultado del aprendizaje o rechazo sin consumir el pergamino.
        """
        if not self.spell_catalog or not command.username:
            return CommandResult.error("Aprendizaje no disponible")
        try:
            spell_id = int(str(item_data.get("HechizoIndex", 0)))
            spell = self.spell_catalog.get_spell_data(spell_id)
            classes = item_data.get("AllowedClasses")
            if not spell or not isinstance(classes, list) or not classes:
                return CommandResult.error("Pergamino sin requisitos válidos")
            rule = ScrollRule(
                item_id,
                spell_id,
                int(str(item_data.get("MinLevel", 1))),
                int(spell.get("min_skill", 0)),
                tuple(int(value) for value in classes),
            )
            result = await learn_scroll(
                self.player_repo.redis.redis,
                command.user_id,
                command.username,
                command.slot,
                command.operation_id,
                rule,
            )
        except RedisError, RuntimeError:
            await self.message_sender.send_console_msg(
                "Aprendizaje sin confirmar. Reconecta para consultar el libro y el inventario."
            )
            return CommandResult.error("Resultado sin confirmar")
        except ValueError, TypeError:
            return CommandResult.error("Pergamino o requisitos inválidos")
        await self.message_sender.send_console_msg(result["message"])
        if not result["applied"]:
            return CommandResult.error(result["message"])
        await notify_inventory(self.message_sender, inventory_repo, command.user_id)
        await self.message_sender.send_change_spell_slot(
            result["book_slot"], spell_id, spell.get("name", "hechizo")
        )
        return CommandResult.ok(data=result)
