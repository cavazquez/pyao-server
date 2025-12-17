"""Handler especializado para drop de oro."""

import logging
from typing import TYPE_CHECKING

# Constantes para el oro
GOLD_ITEM_ID = 12  # ID del item oro en el catálogo
GOLD_GRH_INDEX = 511  # Índice gráfico del oro

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class DropGoldHandler:
    """Handler especializado para drop de oro."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de oro.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.message_sender = message_sender

    async def drop_gold(
        self, user_id: int, quantity: int
    ) -> tuple[bool, str | None, dict[str, int | str] | None]:
        """Tira oro del jugador al suelo.

        Args:
            user_id: ID del jugador.
            quantity: Cantidad de oro a tirar.

        Returns:
            Tupla (success, error_message, result_data).
        """
        # Obtener oro actual del jugador
        current_gold = await self.player_repo.get_gold(user_id)

        # Validar cantidad
        if quantity <= 0:
            await self.message_sender.send_console_msg("Cantidad inválida.")
            return False, "Cantidad inválida", None

        # Ajustar cantidad al mínimo entre lo que tiene y lo que quiere tirar
        actual_quantity = min(quantity, current_gold)

        if actual_quantity == 0:
            await self.message_sender.send_console_msg("No tienes oro para tirar.")
            return False, "No tienes oro para tirar", None

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return False, "No se pudo obtener la posición del jugador", None

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Reducir oro del jugador
        new_gold = current_gold - actual_quantity
        await self.player_repo.update_gold(user_id, new_gold)

        # Enviar UPDATE_USER_STATS al cliente para actualizar GUI
        # Nota: new_gold ya está actualizado en el repositorio
        await self.message_sender.send_update_user_stats_from_repo(user_id, self.player_repo)

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

        return (
            True,
            None,
            {"item_id": GOLD_ITEM_ID, "quantity": actual_quantity, "type": "gold"},
        )
