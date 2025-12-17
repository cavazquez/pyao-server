"""Handler especializado para pickup de oro."""

import logging
from typing import TYPE_CHECKING

from src.models.item_constants import GOLD_ITEM_ID

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class PickupGoldHandler:
    """Handler especializado para pickup de oro."""

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

    async def pickup_gold(
        self, user_id: int, gold: int, map_id: int, x: int, y: int
    ) -> tuple[bool, str | None, dict[str, int | str] | None]:
        """Recoge oro del suelo.

        Args:
            user_id: ID del jugador.
            gold: Cantidad de oro.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Tupla (success, error_message, result_data).
        """
        # Obtener oro actual
        current_gold = await self.player_repo.get_gold(user_id)
        new_gold = current_gold + gold

        # Actualizar oro
        await self.player_repo.update_gold(user_id, new_gold)

        # Enviar UPDATE_USER_STATS al cliente para actualizar GUI
        # TODO: Optimizar para enviar solo el oro en lugar de todos los stats
        # Nota: new_gold ya está actualizado en el repositorio, así que se obtendrá automáticamente
        await self.message_sender.send_update_user_stats_from_repo(user_id, self.player_repo)

        # Remover del suelo
        self.map_manager.remove_ground_item(map_id, x, y, item_index=0)

        # Broadcast OBJECT_DELETE
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_delete(map_id, x, y)

        # Notificar al jugador
        await self.message_sender.send_console_msg(f"Recogiste {gold} monedas de oro.")
        logger.info("Jugador %d recogió %d de oro en (%d,%d)", user_id, gold, x, y)

        return (
            True,
            None,
            {"item_id": GOLD_ITEM_ID, "quantity": gold, "type": "gold"},
        )
