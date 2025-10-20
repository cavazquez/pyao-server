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
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.map_transition_service = map_transition_service
        self.stamina_service = stamina_service
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
        # Parsear dirección
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

        # Verificar que el player_repo esté disponible
        if self.player_repo is None:
            logger.error("PlayerRepository no está disponible para movimiento")
            return

        # Obtener user_id de la sesión
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de movimiento sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Cancelar meditación si está meditando
        is_meditating = await self.player_repo.is_meditating(user_id)
        if is_meditating:
            await self.player_repo.set_meditating(user_id, is_meditating=False)
            await self.message_sender.send_meditate_toggle()
            await self.message_sender.send_console_msg("Dejas de meditar al moverte.")
            logger.info("user_id %d dejó de meditar al moverse", user_id)

        # Consumir stamina por movimiento
        if self.stamina_service:
            can_move = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_WALK,
                message_sender=self.message_sender,
            )

            if not can_move:
                logger.debug("user_id %d no tiene suficiente stamina para moverse", user_id)
                return

        # Obtener posición actual
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
            current_heading = position.get("heading", 3)
            if heading != current_heading:
                await self.player_repo.set_heading(user_id, heading)
                logger.debug("User %d cambió dirección a %d sin moverse", user_id, heading)
            return

        # Validar colisiones con MapManager
        if self.map_manager and not self.map_manager.can_move_to(current_map, new_x, new_y):
            # Posición bloqueada (pared, agua, otro jugador/NPC)
            logger.debug(
                "User %d no puede moverse a (%d,%d) - posición bloqueada", user_id, new_x, new_y
            )
            # Solo cambiar dirección
            current_heading = position.get("heading", 3)
            if heading != current_heading:
                await self.player_repo.set_heading(user_id, heading)
            return

        # Actualizar posición en Redis (incluyendo heading)
        await self.player_repo.set_position(user_id, new_x, new_y, current_map, heading)

        # Actualizar índice espacial
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

        # Broadcast multijugador: notificar movimiento a otros jugadores
        # Nota: NO enviamos POS_UPDATE al cliente que se movió porque causa saltos visuales
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

        # Detectar si estamos en el borde y hay transición
        edge = None

        if heading == HEADING_NORTH and current_y == MIN_MAP_COORDINATE:
            edge = "north"
        elif heading == HEADING_EAST and current_x == MAX_MAP_COORDINATE:
            edge = "east"
        elif heading == HEADING_SOUTH and current_y == MAX_MAP_COORDINATE:
            edge = "south"
        elif heading == HEADING_WEST and current_x == MIN_MAP_COORDINATE:
            edge = "west"

        # Si estamos en un borde, verificar transición
        if edge and self.map_transition_service:
            transition = self.map_transition_service.get_transition(current_map, edge)

            if transition:
                # Cambiar de mapa
                new_map = transition.to_map
                new_x = transition.to_x
                new_y = transition.to_y
                changed_map = True

                logger.info(
                    "Transición de mapa detectada: %d -> %d, pos (%d,%d) -> (%d,%d)",
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
            new_x = min(MAX_MAP_COORDINATE, current_x + 1)
        elif heading == HEADING_SOUTH:
            new_y = min(MAX_MAP_COORDINATE, current_y + 1)
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
        # IMPORTANTE: Orden correcto de packets según protocolo AO

        # 1. Enviar CHANGE_MAP (ID: 21) - Cliente carga nuevo mapa
        await self.message_sender.send_change_map(new_map)

        # 2. Actualizar posición en Redis ANTES de POS_UPDATE
        if self.player_repo:
            await self.player_repo.set_position(user_id, new_x, new_y, new_map)

        # 3. Enviar POS_UPDATE (ID: 22) - Cliente posiciona jugador
        await self.message_sender.send_pos_update(new_x, new_y)

        # 4. Actualizar heading en Redis
        if self.player_repo:
            await self.player_repo.set_heading(user_id, heading)

        # 5. Broadcast CHARACTER_REMOVE en mapa anterior
        if self.broadcast_service:
            await self.broadcast_service.broadcast_character_remove(current_map, user_id)

        # 6. Broadcast CHARACTER_CREATE en nuevo mapa
        # NOTA: Para simplificar, no hacemos broadcast aquí.
        # El jugador aparecerá en el nuevo mapa cuando otros jugadores lo vean moverse.

        logger.info(
            "User %d cambió de mapa: %d -> %d, pos (%d,%d) -> (%d,%d)",
            user_id,
            current_map,
            new_map,
            current_x,
            current_y,
            new_x,
            new_y,
        )
