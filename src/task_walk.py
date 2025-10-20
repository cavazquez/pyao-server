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

    async def execute(self) -> None:  # noqa: PLR0915, PLR0914
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
            # Determinar la razón del bloqueo
            reason = "desconocida"

            # Verificar límites del mapa
            if new_x < 1 or new_x > 100 or new_y < 1 or new_y > 100:  # noqa: PLR2004
                reason = "fuera de límites del mapa"
            # Verificar si es un tile bloqueado del mapa (pared, agua, etc.)
            elif (
                current_map in self.map_manager._blocked_tiles  # noqa: SLF001
                and (new_x, new_y) in self.map_manager._blocked_tiles[current_map]  # noqa: SLF001
            ):
                reason = "tile bloqueado del mapa (pared/agua)"
            # Verificar si está ocupado por jugador o NPC
            else:
                occupant = self.map_manager.get_tile_occupant(current_map, new_x, new_y)
                if occupant:
                    if occupant.startswith("player:"):
                        player_id = occupant.split(":")[1]
                        reason = f"ocupado por jugador {player_id}"
                    elif occupant.startswith("npc:"):
                        npc_id = occupant.split(":")[1]
                        reason = f"ocupado por NPC {npc_id}"

            logger.info(
                "User %d no puede moverse a (%d,%d) en mapa %d - Razón: %s",
                user_id,
                new_x,
                new_y,
                current_map,
                reason,
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

        # Después del movimiento, verificar si estamos en el último tile jugable
        # y si el siguiente tile en la dirección del movimiento está bloqueado
        # Si es así y hay transición, cambiar de mapa
        if changed_map is False and self.map_transition_service and self.map_manager:
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

            if is_next_blocked:
                # El siguiente tile está bloqueado
                # Solo activar transición si estamos CERCA del borde del mapa (últimos 10 tiles)
                map_width, map_height = self.map_manager.get_map_size(new_map)
                near_border = False
                edge = None

                if heading == HEADING_NORTH and check_y <= MIN_MAP_COORDINATE + 10:
                    near_border = True
                    edge = "north"
                elif heading == HEADING_EAST and check_x >= map_width - 10:
                    near_border = True
                    edge = "east"
                elif heading == HEADING_SOUTH and check_y >= map_height - 10:
                    near_border = True
                    edge = "south"
                elif heading == HEADING_WEST and check_x <= MIN_MAP_COORDINATE + 10:
                    near_border = True
                    edge = "west"

                if near_border and edge:
                    transition = self.map_transition_service.get_transition(new_map, edge)
                    if transition:
                        # Hay transición, cambiar de mapa inmediatamente
                        logger.info(
                            "Último tile jugable detectado en (%d,%d), cambiando a mapa %d",
                            new_x,
                            new_y,
                            transition.to_map,
                        )

                        # Actualizar a la nueva posición en el nuevo mapa
                        new_map = transition.to_map
                        new_x = transition.to_x
                        new_y = transition.to_y
                        changed_map = True

                        # Ejecutar la transición
                        await self._handle_map_transition(
                            user_id,
                            heading,
                            current_x,
                            current_y,
                            current_map,
                            new_x,
                            new_y,
                            new_map,
                        )
                        return

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

    async def _calculate_new_position(  # noqa: PLR0915
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

        # Detectar si el siguiente tile está fuera del mapa (transición)
        edge = None

        if next_y < MIN_MAP_COORDINATE:
            edge = "north"
        elif next_x > map_width:
            edge = "east"
        elif next_y > map_height:
            edge = "south"
        elif next_x < MIN_MAP_COORDINATE:
            edge = "west"

        # Verificar si estamos en el último tile jugable antes de un borde bloqueado
        # El cliente no envía movimientos a tiles bloqueados, así que debemos detectar
        # cuando el jugador está en el último tile jugable y hay una transición
        if not edge and self.map_transition_service:
            # Verificar si hay transición en la dirección del movimiento
            potential_edge = None
            if heading == HEADING_NORTH:
                potential_edge = "north"
            elif heading == HEADING_EAST:
                potential_edge = "east"
            elif heading == HEADING_SOUTH:
                potential_edge = "south"
            elif heading == HEADING_WEST:
                potential_edge = "west"

            if potential_edge:
                transition = self.map_transition_service.get_transition(current_map, potential_edge)
                if transition and self.map_manager:
                    # Hay transición configurada, verificar si el siguiente tile está bloqueado
                    is_blocked = not self.map_manager.can_move_to(current_map, next_x, next_y)
                    if is_blocked:
                        # Estamos en el último tile jugable, activar transición
                        edge = potential_edge
                        logger.info(
                            "Último tile jugable (%d,%d), siguiente tile (%d,%d) bloqueado, "
                            "activando transición %s -> mapa %d",
                            current_x,
                            current_y,
                            next_x,
                            next_y,
                            edge,
                            transition.to_map,
                        )

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
            new_x = min(map_width, current_x + 1)
        elif heading == HEADING_SOUTH:
            new_y = min(map_height, current_y + 1)
        elif heading == HEADING_WEST:
            new_x = max(MIN_MAP_COORDINATE, current_x - 1)

        return new_x, new_y, new_map, changed_map

    async def _handle_map_transition(  # noqa: PLR0915
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
        import asyncio  # noqa: PLC0415

        from src.account_repository import AccountRepository  # noqa: PLC0415

        # IMPORTANTE: Orden correcto de packets según protocolo AO

        # 1. Enviar CHANGE_MAP (ID: 21) - Cliente carga nuevo mapa
        await self.message_sender.send_change_map(new_map)

        # 2. Dar tiempo al cliente para cargar el mapa (crítico)
        await asyncio.sleep(0.1)

        # 3. Actualizar posición en Redis ANTES de POS_UPDATE
        if self.player_repo:
            await self.player_repo.set_position(user_id, new_x, new_y, new_map, heading)

        # 4. Enviar POS_UPDATE (ID: 22) - Cliente posiciona jugador
        await self.message_sender.send_pos_update(new_x, new_y)

        # 5. Remover jugador del mapa anterior en MapManager
        if self.map_manager:
            self.map_manager.remove_player(current_map, user_id)

        # 6. Broadcast CHARACTER_REMOVE en mapa anterior
        if self.broadcast_service:
            await self.broadcast_service.broadcast_character_remove(current_map, user_id)

        # 7. Agregar jugador al nuevo mapa en MapManager
        if self.map_manager and self.player_repo:
            account_repo = AccountRepository(self.player_repo.redis)
            account_data = await account_repo.get_account_by_user_id(user_id)
            username = (
                account_data.get("username", f"Player{user_id}")
                if account_data
                else f"Player{user_id}"
            )
            self.map_manager.add_player(new_map, user_id, self.message_sender, username)

        # 8. Enviar CHARACTER_CREATE del propio jugador (para que aparezca en su cliente)
        if self.player_repo:
            account_repo = AccountRepository(self.player_repo.redis)
            account_data = await account_repo.get_account_by_user_id(user_id)

            char_body = 1
            char_head = 1
            username = f"Player{user_id}"

            if account_data:
                char_body = int(account_data.get("char_race", 1))
                char_head = int(account_data.get("char_head", 1))
                username = account_data.get("username", f"Player{user_id}")
                if char_body == 0:
                    char_body = 1

            await self.message_sender.send_character_create(
                char_index=user_id,
                body=char_body,
                head=char_head,
                heading=heading,
                x=new_x,
                y=new_y,
                name=username,
            )

        # 9. Enviar todos los jugadores existentes en el nuevo mapa
        if self.map_manager and self.player_repo:
            existing_players = self.map_manager.get_players_in_map(new_map)
            account_repo = AccountRepository(self.player_repo.redis)

            for other_user_id in existing_players:
                if other_user_id == user_id:
                    continue

                other_position = await self.player_repo.get_position(other_user_id)
                if not other_position:
                    continue

                other_account = await account_repo.get_account_by_user_id(other_user_id)
                if not other_account:
                    continue

                other_body = int(other_account.get("char_race", 1))
                other_head = int(other_account.get("char_head", 1))
                other_username = other_account.get("username", "")

                if other_body == 0:
                    other_body = 1

                await self.message_sender.send_character_create(
                    char_index=other_user_id,
                    body=other_body,
                    head=other_head,
                    heading=other_position.get("heading", 3),
                    x=other_position["x"],
                    y=other_position["y"],
                    name=other_username,
                )
                await asyncio.sleep(0.01)

        # 10. Enviar todos los NPCs del nuevo mapa
        if self.map_manager:
            npcs = self.map_manager.get_npcs_in_map(new_map)
            for npc in npcs:
                await self.message_sender.send_character_create(
                    char_index=npc.char_index,
                    body=npc.body_id,
                    head=npc.head_id,
                    heading=npc.heading,
                    x=npc.x,
                    y=npc.y,
                    weapon=0,
                    shield=0,
                    helmet=0,
                    fx=0,
                    loops=0,
                    name=npc.name,
                )
                await asyncio.sleep(0.01)

        # 11. Enviar todos los objetos del suelo en el nuevo mapa
        if self.map_manager:
            items_sent = 0
            for (item_map_id, x, y), items in self.map_manager._ground_items.items():  # noqa: SLF001
                if item_map_id != new_map:
                    continue

                for item in items:
                    grh_index = item.get("grh_index")
                    if grh_index and isinstance(grh_index, int):
                        await self.message_sender.send_object_create(x, y, grh_index)
                        items_sent += 1
                        await asyncio.sleep(0.01)

            if items_sent > 0:
                logger.info("Enviados %d ground items en transición a mapa %d", items_sent, new_map)

        # 12. Broadcast CHARACTER_CREATE del jugador a otros en el nuevo mapa
        if self.broadcast_service and self.player_repo:
            account_repo = AccountRepository(self.player_repo.redis)
            account_data = await account_repo.get_account_by_user_id(user_id)

            char_body = 1
            char_head = 1
            username = f"Player{user_id}"

            if account_data:
                char_body = int(account_data.get("char_race", 1))
                char_head = int(account_data.get("char_head", 1))
                username = account_data.get("username", f"Player{user_id}")
                if char_body == 0:
                    char_body = 1

            await self.broadcast_service.broadcast_character_create(
                map_id=new_map,
                char_index=user_id,
                body=char_body,
                head=char_head,
                heading=heading,
                x=new_x,
                y=new_y,
                name=username,
            )

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
