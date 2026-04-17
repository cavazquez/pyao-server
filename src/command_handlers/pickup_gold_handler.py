"""Handler especializado para pickup de oro."""

import logging
from typing import TYPE_CHECKING

from src.models.item_constants import GOLD_ITEM_ID, MAX_PLAYER_GOLD

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


class PickupGoldHandler:
    """Handler especializado para pickup de oro.

    Todas las operaciones asumen que el oro ya fue *reclamado* del tile por
    ``PickupCommandHandler`` (claim-first). Si este handler falla, el caller
    debe restaurar el oro al suelo.
    """

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

    async def pickup_claimed_gold(
        self, user_id: int, gold: int, map_id: int, x: int, y: int
    ) -> tuple[bool, str | None, dict[str, int | str] | None]:
        """Acredita oro ya reclamado del tile al inventario del jugador.

        Precondición: ``remove_ground_item`` ya fue invocado por el caller y
        el oro NO está en el suelo.

        Args:
            user_id: ID del jugador.
            gold: Cantidad de oro reclamada.
            map_id: ID del mapa (para broadcast).
            x: Posición X (para broadcast).
            y: Posición Y (para broadcast).

        Returns:
            Tupla ``(success, error_message, result_data)``.

            - ``success=False`` indica que el caller debe restaurar el oro al
              suelo (caso típico: se superaría ``MAX_PLAYER_GOLD``).
        """
        if gold <= 0:
            logger.warning("Cantidad de oro no positiva: %d (user_id=%d)", gold, user_id)
            return False, "Cantidad de oro inválida", None

        current_gold = await self.player_repo.get_gold(user_id)

        if current_gold >= MAX_PLAYER_GOLD:
            await self.message_sender.send_console_msg(
                "No podés cargar más oro, tu bolsa está al tope."
            )
            return False, "Tope de oro alcanzado", None

        new_gold = current_gold + gold
        if new_gold > MAX_PLAYER_GOLD:
            # Capeamos la cantidad aceptada y devolvemos el remanente al suelo
            # vía el caller (success=False con remanente en el mensaje).
            accepted = MAX_PLAYER_GOLD - current_gold
            new_gold = MAX_PLAYER_GOLD
            await self.player_repo.update_gold(user_id, new_gold)
            await self.message_sender.send_update_user_stats_from_repo(user_id, self.player_repo)
            await self.broadcast_deletion(map_id, x, y)
            remainder = gold - accepted
            # Dejar el remanente en el suelo: como el claim removió todo el
            # montón, lo reponemos con la diferencia.
            self.map_manager.add_ground_item(
                map_id,
                x,
                y,
                {"item_id": GOLD_ITEM_ID, "quantity": remainder, "grh_index": None},
            )
            await self.message_sender.send_console_msg(
                f"Recogiste {accepted} monedas de oro (tope alcanzado, quedaron {remainder})."
            )
            logger.info(
                "Jugador %d recogió %d oro (cap); remanente=%d en (%d,%d)",
                user_id,
                accepted,
                remainder,
                x,
                y,
            )
            return (
                True,
                None,
                {"item_id": GOLD_ITEM_ID, "quantity": accepted, "type": "gold"},
            )

        await self.player_repo.update_gold(user_id, new_gold)
        await self.message_sender.send_update_user_stats_from_repo(user_id, self.player_repo)
        await self.broadcast_deletion(map_id, x, y)
        await self.message_sender.send_console_msg(f"Recogiste {gold} monedas de oro.")
        logger.info("Jugador %d recogió %d de oro en (%d,%d)", user_id, gold, x, y)

        return (
            True,
            None,
            {"item_id": GOLD_ITEM_ID, "quantity": gold, "type": "gold"},
        )

    async def broadcast_deletion(self, map_id: int, x: int, y: int) -> None:
        """Notifica a los demás jugadores que el item desapareció del tile."""
        if self.broadcast_service:
            await self.broadcast_service.broadcast_object_delete(map_id, x, y)
