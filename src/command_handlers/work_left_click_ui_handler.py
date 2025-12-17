"""Handler especializado para actualización de UI en trabajo con click."""

import logging
from typing import TYPE_CHECKING

from src.models.items_catalog import get_item

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository

logger = logging.getLogger(__name__)


class WorkLeftClickUIHandler:
    """Handler especializado para actualización de UI en trabajo con click."""

    def __init__(
        self,
        inventory_repo: InventoryRepository,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de UI.

        Args:
            inventory_repo: Repositorio de inventario.
            message_sender: Enviador de mensajes.
        """
        self.inventory_repo = inventory_repo
        self.message_sender = message_sender

    async def update_inventory_ui(self, user_id: int, item_id: int, slot: int) -> None:
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

    async def send_work_messages(
        self,
        resource_name: str,
        quantity: int,
        skill_name: str,
        exp_gained: int,
        leveled_up: bool,
    ) -> None:
        """Envía mensajes al cliente sobre el trabajo realizado.

        Args:
            resource_name: Nombre del recurso obtenido.
            quantity: Cantidad obtenida.
            skill_name: Nombre de la habilidad.
            exp_gained: Experiencia ganada.
            leveled_up: Si subió de nivel.
        """
        # Mensaje principal con el recurso obtenido
        await self.message_sender.console.send_console_msg(
            f"Has obtenido {quantity} {resource_name}"
        )

        # Mensaje de experiencia
        await self.message_sender.console.send_console_msg(f"+{exp_gained} exp en {skill_name}")

        # Mensaje si subió de nivel
        if leveled_up:
            await self.message_sender.console.send_console_msg(
                f"¡¡Has subido de nivel en {skill_name}!!"
            )
