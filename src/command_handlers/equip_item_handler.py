"""Handler para comando de equipar/desequipar item."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.equip_item_command import EquipItemCommand
from src.repositories.inventory_repository import InventoryRepository
from src.services.player.equipment_service import EquipmentService
from src.services.player.player_service import PlayerService

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.equipment_repository import EquipmentRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.player.player_death_service import PlayerDeathService

logger = logging.getLogger(__name__)


class EquipItemCommandHandler(CommandHandler):
    """Handler para comando de equipar/desequipar item (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        equipment_repo: EquipmentRepository,
        message_sender: MessageSender,
        player_death_service: PlayerDeathService | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            equipment_repo: Repositorio de equipamiento.
            message_sender: Enviador de mensajes.
            player_death_service: Publicador común de apariencia y estado confirmado.
        """
        self.player_repo = player_repo
        self.equipment_repo = equipment_repo
        self.message_sender = message_sender
        self.player_death_service = player_death_service

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de equipar/desequipar item (solo lógica de negocio).

        Args:
            command: Comando de equipar/desequipar item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, EquipItemCommand):
            return CommandResult.error("Comando inválido: se esperaba EquipItemCommand")

        user_id = command.user_id
        slot = command.slot

        logger.info(
            "EquipItemCommandHandler: user_id=%d intenta equipar/desequipar item en slot %d",
            user_id,
            slot,
        )

        try:
            # Crear servicio de equipamiento
            inventory_repo = InventoryRepository(self.player_repo.redis)
            equipment_service = EquipmentService(self.equipment_repo, inventory_repo)

            # Equipar o desequipar el item
            success = await equipment_service.toggle_equip_item(user_id, slot, self.message_sender)

            if not success:
                return CommandResult.error("No se pudo equipar/desequipar el item")

            # Reenviar el inventario completo para actualizar el estado de equipamiento
            player_service = PlayerService(self.player_repo, self.message_sender)
            await player_service.send_inventory(user_id, self.equipment_repo)
            if self.player_death_service:
                await self.player_death_service.publish_state(user_id, refresh_inventory=False)

            return CommandResult.ok(data={"slot": slot, "success": True})

        except Exception as e:
            logger.exception("Error al equipar/desequipar item")
            return CommandResult.error(f"Error al equipar/desequipar: {e!s}")
