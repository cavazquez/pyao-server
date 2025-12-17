"""Handler especializado para ejecución de movimiento."""

import logging
from typing import TYPE_CHECKING, Any

from src.models.item_constants import BOAT_ITEM_ID

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.map.player_map_service import PlayerMapService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)

# Constantes para direcciones de movimiento
HEADING_NORTH = 1
HEADING_EAST = 2
HEADING_SOUTH = 3
HEADING_WEST = 4

# Constantes para límites del mapa
MIN_MAP_COORDINATE = 1
MAX_MAP_COORDINATE = 100


class WalkMovementHandler:
    """Handler especializado para ejecución de movimiento."""

    def __init__(
        self,
        player_repo: PlayerRepository | None,
        map_manager: MapManager | None,
        broadcast_service: MultiplayerBroadcastService | None,
        player_map_service: PlayerMapService | None,
        inventory_repo: InventoryRepository | None,
        map_resources: MapResourcesService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de movimiento.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast.
            player_map_service: Servicio de transición de mapas.
            inventory_repo: Repositorio de inventario.
            map_resources: Servicio de recursos de mapa.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.player_map_service = player_map_service
        self.inventory_repo = inventory_repo
        self.map_resources = map_resources
        self.message_sender = message_sender

    async def execute_movement(
        self,
        user_id: int,
        heading: int,
        current_x: int,
        current_y: int,
        current_map: int,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        """Ejecuta el movimiento del jugador.

        Args:
            user_id: ID del usuario.
            heading: Dirección del movimiento.
            current_x: Posición X actual.
            current_y: Posición Y actual.
            current_map: ID del mapa actual.

        Returns:
            Tupla (success, error_message, data).
        """
        # Calcular nueva posición y detectar transiciones de mapa
        new_x, new_y, new_map, changed_map = await self._calculate_new_position(
            heading, current_x, current_y, current_map
        )

        # Si cambió de mapa, manejar transición
        if changed_map:
            await self._handle_map_transition(
                user_id, heading, current_x, current_y, current_map, new_x, new_y, new_map
            )
            return (
                True,
                None,
                {
                    "moved": True,
                    "changed_map": True,
                    "new_map": new_map,
                    "new_x": new_x,
                    "new_y": new_y,
                },
            )

        # Verificar si realmente se movió
        moved = new_x != current_x or new_y != current_y

        if not moved:  # noqa: SIM102
            # No se movió (límite del mapa sin transición)
            # Solo actualizar heading si cambió
            if self.player_repo:
                position = await self.player_repo.get_position(user_id)
                if position:
                    current_heading = position.get("heading", 3)
                    if heading != current_heading:
                        await self.player_repo.set_heading(user_id, heading)
                        logger.debug("User %d cambió dirección a %d sin moverse", user_id, heading)
                    return (
                        True,
                        None,
                        {"moved": False, "heading_changed": heading != current_heading},
                    )

        # Validar colisiones con MapManager
        collision_result = await self._validate_collisions(
            user_id, heading, current_map, new_x, new_y
        )
        if collision_result is not None:
            return collision_result

        # Actualizar posición y broadcast
        position = await self.player_repo.get_position(user_id) if self.player_repo else None
        await self._update_position_and_spatial_index(
            user_id, heading, current_x, current_y, current_map, new_x, new_y
        )

        # Broadcast a otros jugadores
        if position:
            await self._broadcast_movement(
                user_id, heading, current_x, current_y, current_map, new_x, new_y, position
            )

        return (
            True,
            None,
            {
                "moved": True,
                "new_x": new_x,
                "new_y": new_y,
                "map": current_map,
                "heading": heading,
            },
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

    async def _validate_collisions(
        self, user_id: int, heading: int, current_map: int, new_x: int, new_y: int
    ) -> tuple[bool, str | None, dict[str, Any] | None] | None:
        """Valida colisiones y navegación.

        Args:
            user_id: ID del usuario.
            heading: Dirección del movimiento.
            current_map: ID del mapa actual.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.

        Returns:
            Tupla (success, error_message, data) si hay bloqueo, None si puede moverse.
        """
        if not self.map_manager:
            return None

        # Si tenemos información de recursos de mapa, evitar caminar por agua
        # cuando el jugador no está en modo navegación.
        if (
            self.map_resources
            and self.player_repo
            and self.map_resources.has_water(current_map, new_x, new_y)
        ):
            is_sailing = await self.player_repo.is_sailing(user_id)
            if not is_sailing:
                await self.message_sender.send_console_msg(
                    "Necesitas estar navegando para avanzar por el agua."
                )
                logger.info(
                    "Movimiento sobre agua bloqueado sin barca: user_id=%d map=%d pos=(%d,%d)",
                    user_id,
                    current_map,
                    new_x,
                    new_y,
                )
                return (
                    False,
                    "Necesitas estar navegando para avanzar por el agua.",
                    None,
                )

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
                position = (
                    await self.player_repo.get_position(user_id) if self.player_repo else None
                )
                if position:
                    await self._handle_blocked_movement(
                        user_id, heading, current_map, new_x, new_y, position
                    )
                return (True, None, {"moved": False, "blocked": True})

        logger.debug(
            "Movement allowed for user %d -> map=%d (%d,%d) heading=%d",
            user_id,
            current_map,
            new_x,
            new_y,
            heading,
        )

        return None

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

    async def _has_boat(self, user_id: int) -> bool:
        """Verifica si el jugador tiene una barca en su inventario.

        Args:
            user_id: ID del jugador.

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

        Args:
            user_id: ID del jugador.
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

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
