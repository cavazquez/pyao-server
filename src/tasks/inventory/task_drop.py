"""Task para manejar el drop de items del inventario al suelo."""

import logging
from typing import TYPE_CHECKING

from src.network.packet_data import DropData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task

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


class TaskDrop(Task):
    """Maneja el packet DROP del cliente."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        inventory_repo: InventoryRepository | None = None,
        map_manager: MapManager | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el task.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            inventory_repo: Repositorio de inventario.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.inventory_repo = inventory_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Procesa el drop de un item del inventario al suelo."""
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de dropear item sin estar logueado")
            return

        # Parsear datos: slot (u8) + quantity (u16)
        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        slot = validator.read_slot(min_slot=1, max_slot=20)
        quantity = validator.read_quantity(min_qty=1, max_qty=10000)

        if validator.has_errors() or slot is None or quantity is None:
            error_msg = (
                validator.get_error_message() if validator.has_errors() else "Datos inválidos"
            )
            await self.message_sender.send_console_msg(error_msg)
            return

        # Crear dataclass con datos validados
        drop_data = DropData(slot=slot, quantity=quantity)

        logger.info(
            "TaskDrop: user_id=%d slot=%d quantity=%d", user_id, drop_data.slot, drop_data.quantity
        )

        # Validar que tenemos los servicios necesarios
        if not self.player_repo or not self.map_manager:
            logger.error("TaskDrop: Faltan servicios necesarios")
            return

        # El oro se dropea desde el inventario pero es un stat especial
        # Por ahora implementar solo drop de oro
        # TODO: Implementar drop de items reales del inventario

        # Intentar dropear oro (asumimos que cualquier drop es oro por ahora)
        await self._drop_gold(user_id, drop_data.quantity)

    async def _drop_gold(self, user_id: int, quantity: int) -> None:
        """Tira oro del jugador al suelo.

        Args:
            user_id: ID del jugador.
            quantity: Cantidad de oro a tirar.
        """
        if not self.player_repo or not self.map_manager:
            return

        # Obtener oro actual del jugador
        stats = await self.player_repo.get_stats(user_id)
        if not stats:
            return

        current_gold = stats.get("gold", 0)

        # Validar cantidad
        if quantity <= 0:
            await self.message_sender.send_console_msg("Cantidad inválida.")
            return

        # Ajustar cantidad al mínimo entre lo que tiene y lo que quiere tirar
        actual_quantity = min(quantity, current_gold)

        if actual_quantity == 0:
            await self.message_sender.send_console_msg("No tienes oro para tirar.")
            return

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            return

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
                experience=stats.get("exp", 0),
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
