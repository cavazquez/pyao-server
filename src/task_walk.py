"""Tarea para manejar el movimiento de personajes."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.stamina_service import STAMINA_COST_WALK
from src.task import Task

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.map_transition_service import MapTransitionService
    from src.message_sender import MessageSender
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.player_map_service import PlayerMapService
    from src.player_repository import PlayerRepository
    from src.stamina_service import StaminaService

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
        map_transition_service: MapTransitionService | None = None,
        stamina_service: StaminaService | None = None,
        player_map_service: PlayerMapService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de movimiento.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para broadcast.
            broadcast_service: Servicio de broadcast multijugador.
            map_transition_service: Servicio de transiciones entre mapas.
            stamina_service: Servicio de stamina.
            player_map_service: Servicio de mapas de jugador.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.map_transition_service = map_transition_service
        self.stamina_service = stamina_service
        self.player_map_service = player_map_service
        self.session_data = session_data

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
        if self.map_manager and not self.map_manager.can_move_to(current_map, new_x, new_y):
            await self._handle_blocked_movement(
                user_id, heading, current_map, new_x, new_y, position
            )
            return

        # Actualizar posición y broadcast
        await self._update_position_and_spatial_index(
            user_id, heading, current_x, current_y, current_map, new_x, new_y
        )

        # Verificar transición post-movimiento
        if await self._check_post_movement_transition(
            user_id, heading, current_x, current_y, current_map, new_x, new_y, new_map, changed_map
        ):
            return

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
            "User %d no puede moverse a (%d,%d) en mapa %d - Razón: %s",
            user_id,
            new_x,
            new_y,
            current_map,
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
        # Verificar límites del mapa
        if new_x < 1 or new_x > 100 or new_y < 1 or new_y > 100:  # noqa: PLR2004
            return "fuera de límites del mapa"

        if not self.map_manager:
            return "desconocida"

        # Verificar si es un tile bloqueado del mapa (pared, agua, etc.)
        if (
            current_map in self.map_manager._blocked_tiles  # noqa: SLF001
            and (new_x, new_y) in self.map_manager._blocked_tiles[current_map]  # noqa: SLF001
        ):
            return "tile bloqueado del mapa (pared/agua)"

        # Verificar si está ocupado por jugador o NPC
        occupant = self.map_manager.get_tile_occupant(current_map, new_x, new_y)
        if occupant:
            if occupant.startswith("player:"):
                player_id = occupant.split(":")[1]
                return f"ocupado por jugador {player_id}"
            if occupant.startswith("npc:"):
                npc_id = occupant.split(":")[1]
                return f"ocupado por NPC {npc_id}"

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

        logger.info(
            "User %d se movió de (%d,%d) a (%d,%d) en dirección %d",
            user_id,
            current_x,
            current_y,
            new_x,
            new_y,
            heading,
        )

    async def _check_post_movement_transition(
        self,
        user_id: int,
        heading: int,
        current_x: int,
        current_y: int,
        current_map: int,
        new_x: int,
        new_y: int,
        new_map: int,
        changed_map: bool,
    ) -> bool:
        """Verifica si hay transición de mapa después del movimiento.

        Args:
            user_id: ID del jugador.
            heading: Dirección del movimiento.
            current_x: Posición X antes del movimiento.
            current_y: Posición Y antes del movimiento.
            current_map: ID del mapa antes del movimiento.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            new_map: ID del nuevo mapa.
            changed_map: Si ya cambió de mapa.

        Returns:
            True si se ejecutó una transición, False en caso contrario.
        """
        if changed_map or not self.map_transition_service or not self.map_manager:
            return False

        # Calcular el siguiente tile en la dirección del movimiento
        check_x, check_y = new_x, new_y
        if heading == HEADING_NORTH:
            check_y = new_y - 1
        elif heading == HEADING_EAST:
            check_x = new_x + 1
        elif heading == HEADING_SOUTH:
            check_y = new_y + 1
        elif heading == HEADING_WEST:
            check_x = new_x - 1

        # Verificar si ese tile está bloqueado
        is_next_blocked = not self.map_manager.can_move_to(new_map, check_x, check_y)

        logger.info(
            "Verificando siguiente tile (%d,%d) desde (%d,%d): bloqueado=%s",
            check_x,
            check_y,
            new_x,
            new_y,
            is_next_blocked,
        )

        if not is_next_blocked:
            return False

        # El siguiente tile está bloqueado, verificar si hay transición cerca del borde
        map_width, map_height = self.map_manager.get_map_size(new_map)
        edge = self._get_edge_if_near_border(heading, check_x, check_y, map_width, map_height)

        if not edge:
            return False

        transition = self.map_transition_service.get_transition(new_map, edge)
        if not transition:
            return False

        # Hay transición, cambiar de mapa inmediatamente
        logger.info(
            "Último tile jugable detectado en (%d,%d), cambiando a mapa %d",
            new_x,
            new_y,
            transition.to_map,
        )

        await self._handle_map_transition(
            user_id,
            heading,
            current_x,
            current_y,
            current_map,
            transition.to_x,
            transition.to_y,
            transition.to_map,
        )
        return True

    @staticmethod
    def _get_edge_if_near_border(
        heading: int, check_x: int, check_y: int, map_width: int, map_height: int
    ) -> str | None:
        """Determina si estamos cerca del borde del mapa.

        Args:
            heading: Dirección del movimiento.
            check_x: Posición X a verificar.
            check_y: Posición Y a verificar.
            map_width: Ancho del mapa.
            map_height: Alto del mapa.

        Returns:
            Nombre del borde si estamos cerca, None en caso contrario.
        """
        border_threshold = 10

        if heading == HEADING_NORTH and check_y <= MIN_MAP_COORDINATE + border_threshold:
            return "north"
        if heading == HEADING_EAST and check_x >= map_width - border_threshold:
            return "east"
        if heading == HEADING_SOUTH and check_y >= map_height - border_threshold:
            return "south"
        if heading == HEADING_WEST and check_x <= MIN_MAP_COORDINATE + border_threshold:
            return "west"

        return None

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
