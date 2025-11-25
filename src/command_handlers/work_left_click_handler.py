"""Handler para comando de trabajo con click (pesca, tala, minería)."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.work_left_click_command import WorkLeftClickCommand
from src.config.config_manager import ConfigManager, config_manager
from src.constants.items import ResourceItemID, ToolID
from src.models.items_catalog import get_item

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService

logger = logging.getLogger(__name__)

# Tipos de habilidades de trabajo (enum Skill del cliente)
SKILL_TALAR = 9
SKILL_PESCA = 12
SKILL_MINERIA = 13

# Constantes de experiencia (desde configuración)
EXP_LENA = ConfigManager.as_int(config_manager.get("game.work.exp_wood", 10))
EXP_MINERAL = ConfigManager.as_int(config_manager.get("game.work.exp_mineral", 15))
EXP_PESCADO = ConfigManager.as_int(config_manager.get("game.work.exp_fish", 12))


class WorkLeftClickCommandHandler(CommandHandler):
    """Handler para comando de trabajo con click (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_resources: Servicio de recursos del mapa.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de trabajo con click (solo lógica de negocio).

        Args:
            command: Comando de trabajo con click.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, WorkLeftClickCommand):
            return CommandResult.error("Comando inválido: se esperaba WorkLeftClickCommand")

        user_id = command.user_id
        map_id = command.map_id
        target_x = command.target_x
        target_y = command.target_y
        skill_type = command.skill_type

        logger.info(
            "WorkLeftClickCommandHandler: user_id=%d intenta trabajar en mapa=%d, "
            "posición=(%d, %d), skill=%d",
            user_id,
            map_id,
            target_x,
            target_y,
            skill_type,
        )

        try:
            # Verificar distancia
            if not await self._check_distance(user_id, target_x, target_y):
                return CommandResult.error("Debes estar a un tile de distancia para trabajar")

            # Intentar trabajar en la posición clickeada
            work_result = await self._try_work_at_position(
                user_id, map_id, target_x, target_y, skill_type
            )

            if work_result:
                (
                    resource_name,
                    item_id,
                    quantity,
                    slot,
                    skill_name,
                    exp_gained,
                    leveled_up,
                ) = work_result

                # Mensaje principal con el recurso obtenido
                await self.message_sender.console.send_console_msg(
                    f"Has obtenido {quantity} {resource_name}"
                )

                # Mensaje de experiencia
                await self.message_sender.console.send_console_msg(
                    f"+{exp_gained} exp en {skill_name}"
                )

                # Mensaje si subió de nivel
                if leveled_up:
                    await self.message_sender.console.send_console_msg(
                        f"¡¡Has subido de nivel en {skill_name}!!"
                    )

                await self._update_inventory_ui(user_id, item_id, slot)
                logger.info(
                    "Usuario %d obtuvo %d %s (item_id=%d, slot=%d) + %d exp %s",
                    user_id,
                    quantity,
                    resource_name,
                    item_id,
                    slot,
                    exp_gained,
                    skill_name,
                )

                return CommandResult.ok(
                    data={
                        "resource_name": resource_name,
                        "item_id": item_id,
                        "quantity": quantity,
                        "slot": slot,
                        "skill_name": skill_name,
                        "exp_gained": exp_gained,
                        "leveled_up": leveled_up,
                    }
                )
            await self.message_sender.console.send_console_msg(
                "No hay nada para trabajar en esa posición"
            )
            return CommandResult.error("No hay nada para trabajar en esa posición")

        except Exception as e:
            logger.exception("Error al trabajar con click")
            return CommandResult.error(f"Error al trabajar: {e!s}")

    async def _check_distance(self, user_id: int, target_x: int, target_y: int) -> bool:
        """Verifica que el target esté a distancia 1 del jugador.

        Args:
            user_id: ID del usuario.
            target_x: Coordenada X objetivo.
            target_y: Coordenada Y objetivo.

        Returns:
            True si está a distancia válida, False si no.
        """
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.warning("No se pudo obtener posición del jugador %d", user_id)
            return False

        player_x = position["x"]
        player_y = position["y"]

        if max(abs(target_x - player_x), abs(target_y - player_y)) > 1:
            await self.message_sender.console.send_console_msg(
                "Debes estar a un tile de distancia para trabajar."
            )
            logger.info(
                "Usuario %d intentó trabajar demasiado lejos: player=(%d,%d), target=(%d,%d)",
                user_id,
                player_x,
                player_y,
                target_x,
                target_y,
            )
            return False

        return True

    async def _update_inventory_ui(self, user_id: int, item_id: int, slot: int) -> None:
        """Actualiza la UI del inventario del cliente con el item obtenido.

        Args:
            user_id: ID del usuario.
            item_id: ID del item obtenido.
            slot: Slot del inventario donde se agregó el item.
        """
        item = get_item(item_id)
        if item:
            slot_data = await self.inventory_repo.get_slot(user_id, slot)
            if slot_data:
                total_quantity = slot_data[1]
                await self.message_sender.send_change_inventory_slot(
                    slot=slot,
                    item_id=item.item_id,
                    name=item.name,
                    amount=total_quantity,
                    equipped=False,
                    grh_id=item.graphic_id,
                    item_type=item.item_type.to_client_type(),
                    max_hit=item.max_damage or 0,
                    min_hit=item.min_damage or 0,
                    max_def=item.defense or 0,
                    min_def=item.defense or 0,
                    sale_price=float(item.value),
                )

    async def _try_work_at_position(
        self, user_id: int, map_id: int, target_x: int, target_y: int, skill_type: int
    ) -> tuple[str, int, int, int, str, int, bool] | None:
        """Intenta trabajar en una posición específica.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa.
            target_x: Coordenada X del click.
            target_y: Coordenada Y del click.
            skill_type: Tipo de habilidad (9=Talar, 12=Pesca, 13=Minería).

        Returns:
            Tupla (nombre_recurso, item_id, cantidad, slot, skill_nombre, exp_ganada, subio_nivel)
            si se pudo trabajar, None si no.
        """
        if not self.map_resources:
            return None

        inventory = await self.inventory_repo.get_inventory_slots(user_id)

        has_hacha = any(slot.item_id == ToolID.HACHA_LENADOR for slot in inventory.values())
        has_pico = any(slot.item_id == ToolID.PIQUETE_MINERO for slot in inventory.values())
        has_cana = any(slot.item_id == ToolID.CANA_PESCAR for slot in inventory.values())

        # Verificar recursos según el tipo de skill
        if (
            skill_type == SKILL_TALAR
            and has_hacha
            and self.map_resources.has_tree(map_id, target_x, target_y)
        ):
            slots = await self.inventory_repo.add_item(
                user_id, item_id=ResourceItemID.LENA, quantity=5
            )
            if slots:
                # Dar experiencia en talar
                _new_exp, leveled_up = await self.player_repo.add_skill_experience(
                    user_id, "talar", EXP_LENA
                )
                return (
                    "Leña",
                    ResourceItemID.LENA,
                    5,
                    slots[0][0],
                    "Talar",
                    EXP_LENA,
                    leveled_up,
                )
            return None

        if (
            skill_type == SKILL_MINERIA
            and has_pico
            and self.map_resources.has_mine(map_id, target_x, target_y)
        ):
            slots = await self.inventory_repo.add_item(
                user_id, item_id=ResourceItemID.MINERAL_HIERRO, quantity=3
            )
            if slots:
                # Dar experiencia en minería
                _new_exp, leveled_up = await self.player_repo.add_skill_experience(
                    user_id, "mineria", EXP_MINERAL
                )
                return (
                    "Mineral de Hierro",
                    ResourceItemID.MINERAL_HIERRO,
                    3,
                    slots[0][0],
                    "Minería",
                    EXP_MINERAL,
                    leveled_up,
                )
            return None

        if (
            skill_type == SKILL_PESCA
            and has_cana
            and self.map_resources.has_water(map_id, target_x, target_y)
        ):
            slots = await self.inventory_repo.add_item(
                user_id, item_id=ResourceItemID.PESCADO, quantity=2
            )
            if slots:
                # Dar experiencia en pesca
                _new_exp, leveled_up = await self.player_repo.add_skill_experience(
                    user_id, "pesca", EXP_PESCADO
                )
                return (
                    "Pescado",
                    ResourceItemID.PESCADO,
                    2,
                    slots[0][0],
                    "Pesca",
                    EXP_PESCADO,
                    leveled_up,
                )
            return None

        # Si no tiene herramienta
        if not (has_hacha or has_pico or has_cana):
            await self.message_sender.console.send_console_msg(
                "Necesitas una herramienta (hacha, pico o caña de pescar)"
            )

        return None
