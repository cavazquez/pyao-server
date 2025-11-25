"""Handler para comando de soltar item."""

import logging
from typing import TYPE_CHECKING

from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.drop_command import DropCommand

# Constantes para el oro
GOLD_ITEM_ID = 12  # ID del item oro en el catálogo
GOLD_GRH_INDEX = 511  # Índice gráfico del oro

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class DropCommandHandler(CommandHandler):
    """Handler para comando de soltar item (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        inventory_repo: InventoryRepository | None,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de soltar item (solo lógica de negocio).

        Args:
            command: Comando de soltar item.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, DropCommand):
            return CommandResult.error("Comando inválido: se esperaba DropCommand")

        user_id = command.user_id
        slot = command.slot
        quantity = command.quantity

        logger.info("DropCommandHandler: user_id=%d slot=%d quantity=%d", user_id, slot, quantity)

        # El oro se dropea desde el inventario pero es un stat especial
        # Por ahora implementar solo drop de oro
        # TODO: Implementar drop de items reales del inventario

        # Intentar dropear oro (asumimos que cualquier drop es oro por ahora)
        return await self._drop_gold(user_id, quantity)

    async def _drop_gold(self, user_id: int, quantity: int) -> CommandResult:
        """Tira oro del jugador al suelo.

        Args:
            user_id: ID del jugador.
            quantity: Cantidad de oro a tirar.

        Returns:
            Resultado de la ejecución.
        """
        # Obtener oro actual del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return CommandResult.error("No se pudieron obtener los stats del jugador")

        current_gold = stats.get("gold", 0)

        # Validar cantidad
        if quantity <= 0:
            await self.message_sender.send_console_msg("Cantidad inválida.")
            return CommandResult.error("Cantidad inválida")

        # Ajustar cantidad al mínimo entre lo que tiene y lo que quiere tirar
        actual_quantity = min(quantity, current_gold)

        if actual_quantity == 0:
            await self.message_sender.send_console_msg("No tienes oro para tirar.")
            return CommandResult.error("No tienes oro para tirar")

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return CommandResult.error("No se pudo obtener la posición del jugador")

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Reducir oro del jugador
        new_gold = current_gold - actual_quantity
        await self.player_repo.update_gold(user_id, new_gold)

        # Enviar UPDATE_USER_STATS al cliente para actualizar GUI
        stats = await self.player_repo.get_stats(user_id)
        if stats:
            await self.message_sender.send_update_user_stats(
                max_hp=stats.get("max_hp", 100),
                min_hp=stats.get("min_hp", 100),
                max_mana=stats.get("max_mana", 100),
                min_mana=stats.get("min_mana", 100),
                max_sta=stats.get("max_sta", 100),
                min_sta=stats.get("min_sta", 100),
                gold=new_gold,
                level=stats.get("level", 1),
                elu=stats.get("elu", 300),
                experience=stats.get("experience", 0),
            )

        # TODO: La creación de ground items debe estar encapsulada.
        # Crear un método helper o factory para crear ground items consistentemente.
        # Ejemplo: GroundItemFactory.create_gold(quantity) o similar.
        # Esto evita duplicación de código entre TaskDrop, TaskAttack, etc.

        # Crear ground item
        ground_item: dict[str, int | str | None] = {
            "item_id": GOLD_ITEM_ID,
            "quantity": actual_quantity,
            "grh_index": GOLD_GRH_INDEX,
            "owner_id": None,
            "spawn_time": None,
        }

        # Agregar al MapManager
        self.map_manager.add_ground_item(map_id=map_id, x=x, y=y, item=ground_item)

        # Broadcast OBJECT_CREATE a jugadores cercanos
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_create(
                map_id=map_id, x=x, y=y, grh_index=GOLD_GRH_INDEX
            )

        # Notificar al jugador
        await self.message_sender.send_console_msg(
            f"Tiraste {actual_quantity} monedas de oro al suelo."
        )
        logger.info("Jugador %d tiró %d de oro en (%d,%d)", user_id, actual_quantity, x, y)

        return CommandResult.ok(
            data={"item_id": GOLD_ITEM_ID, "quantity": actual_quantity, "type": "gold"}
        )
