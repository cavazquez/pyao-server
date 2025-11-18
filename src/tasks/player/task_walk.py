"""Tarea para manejar el movimiento de personajes."""

import logging
from typing import TYPE_CHECKING

from src.models.item_constants import BOAT_ITEM_ID
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.services.player.stamina_service import STAMINA_COST_WALK
from src.tasks.task import Task

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.map.player_map_service import PlayerMapService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)

# Constantes para direcciones de movimiento
HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4

# Constantes para validación de paquetes
MIN_WALK_PACKET_SIZE = 2

# Constantes para límites del mapa
MIN_MAP_COORDINATE = 1
MAX_MAP_COORDINATE = 100


class TaskWalk(Task):
    """Tarea que maneja el movimiento de personajes."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        stamina_service: StaminaService | None = None,
        player_map_service: PlayerMapService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
        inventory_repo: InventoryRepository | None = None,
        map_resources: MapResourcesService | None = None,
    ) -> None:
        """Inicializa la tarea de movimiento.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes al cliente.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast a otros jugadores.
            stamina_service: Servicio de stamina para validar y consumir energía.
            player_map_service: Servicio de transición de mapas.
            session_data: Datos de sesión compartidos.
            inventory_repo: Repositorio de inventario del jugador, usado para
                verificar items como la barca al mover.
            map_resources: Servicio de recursos de mapa (agua, árboles, minas),
                utilizado para validar movimiento sobre agua y terrenos especiales.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.stamina_service = stamina_service
        self.player_map_service = player_map_service
        self.session_data = session_data
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources

    def _parse_packet(self) -> int | None:
        """Parsea el paquete de movimiento.

        El formato esperado es:
        - Byte 0: PacketID (WALK = 6)
        - Byte 1: Dirección (1=Norte, 2=Este, 3=Sur, 4=Oeste)

        Returns:
            Dirección del movimiento o None si hay error.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)
        heading = validator.read_heading()

        if validator.has_errors() or heading is None:
            return None

        return heading

    async def execute(self) -> None:
        """Ejecuta el movimiento del personaje."""
        # Parsear y validar packet
        heading = self._parse_packet()
        if heading is None:
            logger.warning(
                "Paquete de movimiento inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        logger.debug(
            "TaskWalk: Recibido WALK con heading=%d desde %s",
            heading,
            self.message_sender.connection.address,
        )

        # Validar dependencias y obtener user_id
        if not self._validate_dependencies():
            return

        user_id = self._get_user_id()
        if user_id is None:
            return

        # Cancelar meditación y consumir stamina
        await self._cancel_meditation_if_active(user_id)

        if not await self._consume_stamina(user_id):
            return

        # Obtener posición actual
        if self.player_repo is None:
            return

        position = await self.player_repo.get_position(user_id)
        if position is None:
            logger.warning("No se encontró posición para user_id %d", user_id)
            return

        current_x = position["x"]
        current_y = position["y"]
        current_map = position["map"]

        # Calcular nueva posición y detectar transiciones de mapa
        new_x, new_y, new_map, changed_map = await self._calculate_new_position(
            heading, current_x, current_y, current_map
        )

        # Si cambió de mapa, manejar transición
        if changed_map:
            await self._handle_map_transition(
                user_id, heading, current_x, current_y, current_map, new_x, new_y, new_map
            )
            return

        # Verificar si realmente se movió
        moved = new_x != current_x or new_y != current_y

        if not moved:
            # No se movió (límite del mapa sin transición)
            # Solo actualizar heading si cambió
            if self.player_repo:
                current_heading = position.get("heading", 3)
                if heading != current_heading:
                    await self.player_repo.set_heading(user_id, heading)
                    logger.debug("User %d cambió dirección a %d sin moverse", user_id, heading)
            return

        # Validar colisiones con MapManager
        if self.map_manager:
            # Si tenemos información de recursos de mapa, evitar caminar por agua
            # cuando el jugador no está en modo navegación.
            if (
                self.map_resources
                and self.player_repo
                and self.map_resources.has_water(current_map, new_x, new_y)
            ):
                is_sailing = await self.player_repo.is_sailing(user_id)
                if not is_sailing:
                    await self.message_sender.console.send_console_msg(
                        "Necesitas estar navegando para avanzar por el agua."
                    )
                    logger.info(
                        "Movimiento sobre agua bloqueado sin barca: user_id=%d map=%d pos=(%d,%d)",
                        user_id,
                        current_map,
                        new_x,
                        new_y,
                    )
                    return

            can_move = self.map_manager.can_move_to(current_map, new_x, new_y)
            if not can_move:
                # Intentar navegar sobre agua si el jugador tiene una barca
                if await self._can_sail_to(user_id, current_map, new_x, new_y):
                    logger.info(
                        "Movimiento sobre agua permitido por barco: user_id=%d map=%d pos=(%d,%d)",
                        user_id,
                        current_map,
                        new_x,
                        new_y,
                    )
                else:
                    await self._handle_blocked_movement(
                        user_id, heading, current_map, new_x, new_y, position
                    )
                    return

            logger.debug(
                "Movement allowed for user %d -> map=%d (%d,%d) heading=%d",
                user_id,
                current_map,
                new_x,
                new_y,
                heading,
            )

        # Actualizar posición y broadcast
        await self._update_position_and_spatial_index(
            user_id, heading, current_x, current_y, current_map, new_x, new_y
        )

        # Verificar transición post-movimiento
        # Broadcast a otros jugadores
        await self._broadcast_movement(
            user_id, heading, current_x, current_y, current_map, new_x, new_y, position
        )

    async def _calculate_new_position(
        self, heading: int, current_x: int, current_y: int, current_map: int
    ) -> tuple[int, int, int, bool]:
        """Calcula nueva posición y detecta transiciones de mapa.

        Args:
            heading: Dirección del movimiento.
            current_x: Posición X actual.
            current_y: Posición Y actual.
            current_map: ID del mapa actual.

        Returns:
            Tupla (new_x, new_y, new_map, changed_map).
        """
        new_x = current_x
        new_y = current_y
        new_map = current_map
        changed_map = False

        # Calcular la posición tentativa del siguiente movimiento
        next_x = current_x
        next_y = current_y

        if heading == HEADING_NORTH:
            next_y = current_y - 1
        elif heading == HEADING_EAST:
            next_x = current_x + 1
        elif heading == HEADING_SOUTH:
            next_y = current_y + 1
        elif heading == HEADING_WEST:
            next_x = current_x - 1

        # Obtener tamaño del mapa actual
        if self.map_manager:
            map_width, map_height = self.map_manager.get_map_size(current_map)
        else:
            map_width, map_height = MAX_MAP_COORDINATE, MAX_MAP_COORDINATE

        # Verificar si el jugador intenta moverse a un tile de exit
        if self.map_manager:
            exit_tile = self.map_manager.get_exit_tile(current_map, next_x, next_y)
            if exit_tile:
                # El tile destino es un exit, activar transición
                new_map = exit_tile["to_map"]
                new_x = exit_tile["to_x"]
                new_y = exit_tile["to_y"]
                changed_map = True

                logger.info(
                    "Exit tile detectado en (%d,%d): Transición %d -> %d, pos (%d,%d) -> (%d,%d)",
                    next_x,
                    next_y,
                    current_map,
                    new_map,
                    current_x,
                    current_y,
                    new_x,
                    new_y,
                )

                return new_x, new_y, new_map, changed_map

        # Movimiento normal (sin transición)
        if heading == HEADING_NORTH:
            new_y = max(MIN_MAP_COORDINATE, current_y - 1)
        elif heading == HEADING_EAST:
            new_x = min(map_width, current_x + 1)
        elif heading == HEADING_SOUTH:
            new_y = min(map_height, current_y + 1)
        elif heading == HEADING_WEST:
            new_x = max(MIN_MAP_COORDINATE, current_x - 1)

        return new_x, new_y, new_map, changed_map

    async def _handle_map_transition(
        self,
        user_id: int,
        heading: int,
        current_x: int,
        current_y: int,
        current_map: int,
        new_x: int,
        new_y: int,
        new_map: int,
    ) -> None:
        """Maneja la transición de un jugador a un nuevo mapa.

        Args:
            user_id: ID del jugador.
            heading: Dirección del movimiento.
            current_x: Posición X actual.
            current_y: Posición Y actual.
            current_map: ID del mapa actual.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            new_map: ID del nuevo mapa.
        """
        # Usar PlayerMapService para manejar la transición
        if self.player_map_service:
            await self.player_map_service.transition_to_map(
                user_id=user_id,
                current_map=current_map,
                current_x=current_x,
                current_y=current_y,
                new_map=new_map,
                new_x=new_x,
                new_y=new_y,
                heading=heading,
                message_sender=self.message_sender,
            )
        else:
            logger.error("PlayerMapService no disponible para transición de mapa")

    def _validate_dependencies(self) -> bool:
        """Valida que las dependencias necesarias estén disponibles.

        Returns:
            True si todas las dependencias están disponibles, False en caso contrario.
        """
        if self.player_repo is None:
            logger.error("PlayerRepository no está disponible para movimiento")
            return False
        return True

    def _get_user_id(self) -> int | None:
        """Obtiene y valida el user_id de la sesión.

        Returns:
            user_id si es válido, None en caso contrario.
        """
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de movimiento sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return None

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return None

        return int(user_id_value)

    async def _cancel_meditation_if_active(self, user_id: int) -> None:
        """Cancela la meditación si el jugador está meditando.

        Args:
            user_id: ID del jugador.
        """
        if self.player_repo is None:
            return

        is_meditating = await self.player_repo.is_meditating(user_id)
        if is_meditating:
            await self.player_repo.set_meditating(user_id, is_meditating=False)
            await self.message_sender.send_meditate_toggle()
            await self.message_sender.send_console_msg("Dejas de meditar al moverte.")
            logger.info("user_id %d dejó de meditar al moverse", user_id)

    async def _consume_stamina(self, user_id: int) -> bool:
        """Consume stamina por el movimiento.

        Args:
            user_id: ID del jugador.

        Returns:
            True si se pudo consumir stamina, False si no tiene suficiente.
        """
        if self.stamina_service:
            can_move = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_WALK,
                message_sender=self.message_sender,
            )

            if not can_move:
                logger.debug("user_id %d no tiene suficiente stamina para moverse", user_id)
                return False

        return True

    async def _has_boat(self, user_id: int) -> bool:
        """Verifica si el jugador tiene una barca en su inventario.

        Returns:
            True si el jugador posee una barca en algún slot del inventario,
            False en caso contrario.
        """
        if not self.inventory_repo:
            return False

        inventory = await self.inventory_repo.get_inventory_slots(user_id)
        return any(slot.item_id == BOAT_ITEM_ID for slot in inventory.values())

    async def _can_sail_to(self, user_id: int, map_id: int, x: int, y: int) -> bool:
        """Determina si el jugador puede moverse a un tile de agua usando una barca.

        Returns:
            True si el movimiento al tile destino es válido para navegar,
            False si el movimiento no está permitido.
        """
        if not self.map_resources or not self.map_manager or not self.player_repo:
            return False

        if not self.map_resources.has_water(map_id, x, y):
            return False

        # No permitir navegar sobre tiles ocupados
        if self.map_manager.get_tile_occupant(map_id, x, y):
            return False

        # Requiere estar en modo navegación y tener la barca en inventario
        if not await self.player_repo.is_sailing(user_id):
            return False

        return await self._has_boat(user_id)

    async def _handle_blocked_movement(
        self,
        user_id: int,
        heading: int,
        current_map: int,
        new_x: int,
        new_y: int,
        position: dict[str, int],
    ) -> None:
        """Maneja el caso cuando el movimiento está bloqueado.

        Args:
            user_id: ID del jugador.
            heading: Dirección del movimiento.
            current_map: ID del mapa actual.
            new_x: Nueva posición X (bloqueada).
            new_y: Nueva posición Y (bloqueada).
            position: Posición actual del jugador.
        """
        reason = self._get_block_reason(current_map, new_x, new_y)

        logger.info(
            "Movimiento bloqueado: user_id=%d -> mapa=%d (%d,%d) heading=%d - razón=%s",
            user_id,
            current_map,
            new_x,
            new_y,
            heading,
            reason,
        )

        # Solo cambiar dirección
        if self.player_repo:
            current_heading = position.get("heading", 3)
            if heading != current_heading:
                await self.player_repo.set_heading(user_id, heading)

    def _get_block_reason(self, current_map: int, new_x: int, new_y: int) -> str:
        """Determina la razón por la cual un tile está bloqueado.

        Args:
            current_map: ID del mapa.
            new_x: Posición X del tile.
            new_y: Posición Y del tile.

        Returns:
            Descripción de la razón del bloqueo.
        """
        if not self.map_manager:
            return "desconocida"

        reason = self.map_manager.get_tile_block_reason(current_map, new_x, new_y)
        if reason is not None:
            return reason

        return "desconocida"

    async def _update_position_and_spatial_index(
        self,
        user_id: int,
        heading: int,
        current_x: int,
        current_y: int,
        current_map: int,
        new_x: int,
        new_y: int,
    ) -> None:
        """Actualiza la posición del jugador en Redis y el índice espacial.

        Args:
            user_id: ID del jugador.
            heading: Dirección del movimiento.
            current_x: Posición X actual.
            current_y: Posición Y actual.
            current_map: ID del mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
        """
        if self.player_repo:
            await self.player_repo.set_position(user_id, new_x, new_y, current_map, heading)

        if self.map_manager:
            self.map_manager.update_player_tile(
                user_id, current_map, current_x, current_y, new_x, new_y
            )

        logger.debug(
            "User %d se movió de (%d,%d) a (%d,%d) en dirección %d",
            user_id,
            current_x,
            current_y,
            new_x,
            new_y,
            heading,
        )

    async def _broadcast_movement(
        self,
        user_id: int,
        heading: int,
        current_x: int,
        current_y: int,
        current_map: int,
        new_x: int,
        new_y: int,
        position: dict[str, int],
    ) -> None:
        """Hace broadcast del movimiento a otros jugadores.

        Args:
            user_id: ID del jugador.
            heading: Dirección del movimiento.
            current_x: Posición X anterior.
            current_y: Posición Y anterior.
            current_map: ID del mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            position: Posición completa del jugador.
        """
        if self.broadcast_service:
            await self.broadcast_service.broadcast_character_move(
                map_id=current_map,
                char_index=user_id,
                new_x=new_x,
                new_y=new_y,
                new_heading=heading,
                old_x=current_x,
                old_y=current_y,
                old_heading=position.get("heading", 3),
            )
