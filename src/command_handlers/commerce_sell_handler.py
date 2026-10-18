"""Handler para comando de vender item."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.commerce_sell_command import CommerceSellCommand
from src.services.inventory_notifications import notify_inventory

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.commerce_service import CommerceService
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class CommerceSellCommandHandler(CommandHandler):
    """Handler para comando de vender item (solo lógica de negocio)."""

    def __init__(
        self,
        commerce_service: CommerceService,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository,
        redis_client: RedisClient,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            commerce_service: Servicio de comercio.
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            redis_client: Cliente Redis.
            message_sender: Enviador de mensajes.
        """
        self.commerce_service = commerce_service
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.redis_client = redis_client
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de vender item (solo lógica de negocio).

        Args:
            command: Comando de vender item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, CommerceSellCommand):
            return CommandResult.error("Comando inválido: se esperaba CommerceSellCommand")

        user_id = command.user_id
        slot = command.slot
        quantity = command.quantity

        logger.debug(
            "CommerceSellCommandHandler: user_id=%d slot=%d quantity=%d", user_id, slot, quantity
        )

        # Obtener NPC mercader activo de la sesión
        npc_id = await self._get_active_merchant(user_id)
        if not npc_id:
            await self.message_sender.send_console_msg("No tienes una ventana de comercio abierta")
            return CommandResult.error("No tienes una ventana de comercio abierta")

        # Ejecutar venta
        success, message = await self.commerce_service.sell_item(
            user_id, npc_id, slot, quantity, operation_id=command.operation_id
        )

        await self.commerce_service.notify_merchant(self.message_sender, npc_id)

        # Enviar mensaje de resultado
        await self.message_sender.send_console_msg(message)

        if success:
            # Actualizar oro del jugador
            await self._update_player_gold(user_id)

            # Actualizar inventario del jugador
            await self._update_player_inventory(user_id)

            return CommandResult.ok(
                data={"npc_id": npc_id, "slot": slot, "quantity": quantity, "success": True}
            )

        return CommandResult.error(message)

    async def _get_active_merchant(self, user_id: int) -> int | None:
        """Obtiene el ID del mercader activo para el jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            ID del mercader activo o None si no hay comercio activo.
        """
        return await self.redis_client.get_active_merchant(user_id)

    async def _update_player_gold(self, user_id: int) -> None:
        """Envía actualización de oro al cliente.

        Args:
            user_id: ID del jugador.
        """
        gold = await self.player_repo.get_gold(user_id)
        await self.message_sender.send_update_gold(gold)

    async def _update_player_inventory(self, user_id: int) -> None:
        """Sincroniza slots confirmados preservando el equipamiento existente."""
        await notify_inventory(self.message_sender, self.inventory_repo, user_id)
