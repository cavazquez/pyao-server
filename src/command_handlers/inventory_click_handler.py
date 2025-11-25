"""Handler para comando de click en inventario."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.inventory_click_command import InventoryClickCommand
from src.models.items_catalog import get_item
from src.repositories.inventory_repository import InventoryRepository

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Skills: Talar=9, Pesca=12, Minería=13 (ver enums.gd)
WORK_TOOLS: dict[int, int] = {
    561: 9,  # Hacha de Leñador → Talar (Skill.Talar)
    562: 13,  # Piquete de Minero → Minería (Skill.Mineria)
    563: 12,  # Caña de pescar → Pesca (Skill.Pesca)
}


class InventoryClickCommandHandler(CommandHandler):
    """Handler para comando de click en inventario (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        equipment_repo: EquipmentRepository | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            equipment_repo: Repositorio de equipamiento.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.equipment_repo = equipment_repo
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de click en inventario (solo lógica de negocio).

        Args:
            command: Comando de click en inventario.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, InventoryClickCommand):
            return CommandResult.error("Comando inválido: se esperaba InventoryClickCommand")

        user_id = command.user_id
        slot = command.slot

        logger.info("InventoryClickCommandHandler: user_id=%d hace click en slot %d", user_id, slot)

        try:
            # Obtener el inventario
            inventory_repo = InventoryRepository(self.player_repo.redis)
            slot_data = await inventory_repo.get_slot(user_id, slot)

            if not slot_data:
                # Slot vacío - enviar actualización con slot vacío
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
                return CommandResult.ok(data={"slot": slot, "empty": True})

            item_id, quantity = slot_data

            # Obtener el item del catálogo
            item = get_item(item_id)
            if not item:
                logger.error("Item %d no encontrado en catálogo", item_id)
                await self.message_sender.send_console_msg("Item no válido.")
                return CommandResult.error("Item no válido")

            # Verificar si el item está equipado
            is_equipped = False
            if self.equipment_repo:
                equipped_slot = await self.equipment_repo.is_slot_equipped(user_id, slot)
                is_equipped = equipped_slot is not None

            # Enviar información del slot actualizada
            await self.message_sender.send_change_inventory_slot(
                slot=slot,
                item_id=item.item_id,
                name=item.name,
                amount=quantity,
                equipped=is_equipped,
                grh_id=item.graphic_id,
                item_type=item.item_type.to_client_type(),
                max_hit=item.max_damage or 0,
                min_hit=item.min_damage or 0,
                max_def=item.defense or 0,
                min_def=item.defense or 0,
                sale_price=float(item.value),
            )

            logger.info(
                "user_id %d - Slot %d: %s x%d (GrhIndex: %d)",
                user_id,
                slot,
                item.name,
                quantity,
                item.graphic_id,
            )

            # Detectar herramientas y cambiar cursor al modo de trabajo
            # Solo si presionas U en el slot de la herramienta Y está equipada
            if item_id in WORK_TOOLS:
                # Verificar si está equipado
                if is_equipped:
                    skill_type = WORK_TOOLS[item_id]
                    await self.message_sender.send_work_request_target(skill_type)
                    logger.info("Cursor cambiado a modo trabajo: skill_type=%d", skill_type)
                else:
                    await self.message_sender.send_console_msg(
                        "Debes tener equipada la herramienta para trabajar."
                    )

            return CommandResult.ok(
                data={
                    "slot": slot,
                    "item_id": item_id,
                    "quantity": quantity,
                    "is_equipped": is_equipped,
                }
            )

        except Exception as e:
            logger.exception("Error procesando INVENTORY_CLICK")
            return CommandResult.error(f"Error al procesar click en inventario: {e!s}")
