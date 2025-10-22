"""Servicio para broadcast multijugador."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.repositories.account_repository import AccountRepository
    from src.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class MultiplayerBroadcastService:
    """Servicio que encapsula la lógica de broadcast multijugador."""

    # Rango visible en tiles (15 tiles = 31x31 grid centrado en el jugador)
    VISIBLE_RANGE = 15

    def __init__(
        self,
        map_manager: "MapManager",  # noqa: UP037
        player_repo: "PlayerRepository",  # noqa: UP037
        account_repo: "AccountRepository",  # noqa: UP037
    ) -> None:
        """Inicializa el servicio de broadcast multijugador.

        Args:
            map_manager: Gestor de mapas.
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
        """
        self.map_manager = map_manager
        self.player_repo = player_repo
        self.account_repo = account_repo

    @staticmethod
    def _is_in_visible_range(x1: int, y1: int, x2: int, y2: int, visible_range: int) -> bool:
        """Verifica si dos posiciones están dentro del rango visible.

        Usa distancia de Chebyshev (máximo de diferencias absolutas).

        Args:
            x1: Coordenada X de la primera posición.
            y1: Coordenada Y de la primera posición.
            x2: Coordenada X de la segunda posición.
            y2: Coordenada Y de la segunda posición.
            visible_range: Rango visible en tiles.

        Returns:
            True si están en rango visible, False si no.
        """
        return max(abs(x1 - x2), abs(y1 - y2)) <= visible_range

    async def notify_player_spawn(
        self,
        user_id: int,
        username: str,
        position: dict[str, int],
        message_sender: MessageSender,
    ) -> None:
        """Notifica el spawn de un jugador a todos en el mapa.

        Realiza tres acciones:
        1. Envía CHARACTER_CREATE de jugadores existentes al nuevo jugador
        2. Agrega el nuevo jugador al MapManager
        3. Notifica a otros jugadores del nuevo spawn

        Args:
            user_id: ID del usuario que hace spawn.
            username: Nombre del usuario.
            position: Posición del jugador (x, y, map).
            message_sender: MessageSender del nuevo jugador.
        """
        map_id = position["map"]

        # 1. Enviar CHARACTER_CREATE de todos los jugadores existentes al nuevo jugador
        await self._send_existing_players_to_new_player(map_id, message_sender)

        # 2. Agregar el nuevo jugador al MapManager
        self.map_manager.add_player(map_id, user_id, message_sender, username)

        # 3. Enviar CHARACTER_CREATE del nuevo jugador a todos los demás en el mapa
        notified_count = await self._broadcast_new_player_to_others(
            user_id, username, position, map_id
        )

        logger.info(
            "Jugador %d agregado al mapa %d. Notificados %d jugadores",
            user_id,
            map_id,
            notified_count,
        )

    async def _send_existing_players_to_new_player(
        self,
        map_id: int,
        message_sender: MessageSender,
    ) -> None:
        """Envía CHARACTER_CREATE de jugadores existentes al nuevo jugador.

        Args:
            map_id: ID del mapa.
            message_sender: MessageSender del nuevo jugador.
        """
        existing_players = self.map_manager.get_players_in_map(map_id)

        for other_user_id in existing_players:
            # Obtener datos del otro jugador
            other_position = await self.player_repo.get_position(other_user_id)
            if not other_position:
                continue

            # Obtener datos visuales del otro jugador
            other_account = await self.account_repo.get_account_by_user_id(other_user_id)
            if not other_account:
                continue

            other_body = int(other_account.get("char_race", 1))
            other_head = int(other_account.get("char_head", 1))
            other_username = other_account.get("username", "")

            # Validar body (no puede ser 0)
            if other_body == 0:
                other_body = 1

            # Enviar CHARACTER_CREATE del otro jugador al nuevo jugador
            await message_sender.send_character_create(
                char_index=other_user_id,
                body=other_body,
                head=other_head,
                heading=other_position.get("heading", 3),
                x=other_position["x"],
                y=other_position["y"],
                name=other_username,
            )

    async def _broadcast_new_player_to_others(
        self,
        user_id: int,
        username: str,
        position: dict[str, int],
        map_id: int,
    ) -> int:
        """Envía CHARACTER_CREATE del nuevo jugador a todos los demás en el mapa.

        Args:
            user_id: ID del nuevo jugador.
            username: Nombre del nuevo jugador.
            position: Posición del nuevo jugador.
            map_id: ID del mapa.

        Returns:
            Número de jugadores notificados.
        """
        # Obtener body, head, heading desde Redis
        char_body = 1  # Valor por defecto
        char_head = 1  # Valor por defecto
        char_heading = position.get("heading", 3)  # Sur por defecto

        if self.account_repo:
            account_data = await self.account_repo.get_account(username)
            if account_data:
                char_body = int(account_data.get("char_race", 1))
                char_head = int(account_data.get("char_head", 1))
                # Si body es 0, usar valor por defecto
                if char_body == 0:
                    char_body = 1

        other_senders = self.map_manager.get_all_message_senders_in_map(
            map_id, exclude_user_id=user_id
        )

        for sender in other_senders:
            await sender.send_character_create(
                char_index=user_id,
                body=char_body,
                head=char_head,
                heading=char_heading,
                x=position["x"],
                y=position["y"],
                name=username,
            )

        return len(other_senders)

    async def broadcast_character_move(
        self,
        map_id: int,
        char_index: int,
        new_x: int,
        new_y: int,
        new_heading: int,
        old_x: int,
        old_y: int,
        old_heading: int | None = None,
    ) -> int:
        """Envía CHARACTER_MOVE a jugadores cercanos que pueden ver el movimiento.

        Args:
            map_id: ID del mapa donde ocurre el movimiento.
            char_index: Índice del personaje que se mueve.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            new_heading: Nueva dirección.
            old_x: Posición X anterior.
            old_y: Posición Y anterior.
            old_heading: Dirección anterior (opcional, para detectar cambios).

        Returns:
            Número de jugadores notificados.
        """
        # Obtener todos los jugadores en el mapa (excluyendo el que se movió para evitar saltos)
        all_player_ids = self.map_manager.get_players_in_map(map_id, exclude_user_id=char_index)

        notified = 0
        for player_id in all_player_ids:
            # Obtener posición del jugador para verificar si está en rango visible
            player_position = await self.player_repo.get_position(player_id)
            if not player_position:
                continue

            # Filtrar por rango visible
            if not self._is_in_visible_range(
                new_x, new_y, player_position["x"], player_position["y"], self.VISIBLE_RANGE
            ):
                continue

            # Obtener message_sender del jugador
            sender = self.map_manager.get_message_sender(player_id, map_id)
            if not sender:
                continue

            # Enviar el movimiento solo a jugadores en rango visible
            await sender.send_character_move(char_index, new_x, new_y)

            # Solo enviar CHARACTER_CHANGE si el heading cambió
            # (CHARACTER_MOVE no incluye heading para compatibilidad con cliente Godot)
            if old_heading is None or new_heading != old_heading:
                # Obtener body y head desde Redis
                char_body = 1  # Valor por defecto
                char_head = 1  # Valor por defecto

                # Obtener username del char_index
                username = self.map_manager.get_username(char_index, map_id)
                if username and self.account_repo:
                    account_data = await self.account_repo.get_account(username)
                    if account_data:
                        char_body = int(account_data.get("char_race", 1))
                        char_head = int(account_data.get("char_head", 1))
                        # Si body es 0, usar valor por defecto
                        if char_body == 0:
                            char_body = 1

                await sender.send_character_change(
                    char_index, body=char_body, head=char_head, heading=new_heading
                )
            notified += 1

        if notified > 0:
            logger.debug(
                "Broadcast CHARACTER_MOVE: CharIndex=%d de (%d,%d) a (%d,%d) - %d notificados",
                char_index,
                old_x,
                old_y,
                new_x,
                new_y,
                notified,
            )

        return notified

    async def broadcast_character_create(
        self,
        map_id: int,
        char_index: int,
        body: int,
        head: int,
        heading: int,
        x: int,
        y: int,
        name: str,
    ) -> int:
        """Broadcast de CHARACTER_CREATE a todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            char_index: Índice del personaje.
            body: ID del cuerpo.
            head: ID de la cabeza.
            heading: Dirección del personaje.
            x: Posición X.
            y: Posición Y.
            name: Nombre del personaje.

        Returns:
            Número de jugadores notificados.
        """
        # Obtener todos los jugadores en el mapa
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)

        notified = 0
        for sender in all_senders:
            await sender.send_character_create(
                char_index=char_index,
                body=body,
                head=head,
                heading=heading,
                x=x,
                y=y,
                name=name,
            )
            notified += 1

        if notified > 0:
            logger.debug(
                "Broadcast CHARACTER_CREATE: %s (CharIndex=%d) en (%d,%d) - %d notificados",
                name,
                char_index,
                x,
                y,
                notified,
            )

        return notified

    async def broadcast_character_remove(self, map_id: int, char_index: int) -> int:
        """Broadcast de CHARACTER_REMOVE a todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            char_index: Índice del personaje que se remueve.

        Returns:
            Número de jugadores notificados.
        """
        # Obtener todos los jugadores en el mapa
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)

        notified = 0
        for sender in all_senders:
            await sender.send_character_remove(char_index)
            notified += 1

        if notified > 0:
            logger.debug(
                "Broadcast CHARACTER_REMOVE: CharIndex=%d - %d notificados", char_index, notified
            )

        return notified

    async def broadcast_block_position(self, map_id: int, x: int, y: int, blocked: bool) -> int:
        """Broadcast de BLOCK_POSITION a todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            x: Posición X del tile.
            y: Posición Y del tile.
            blocked: True si está bloqueado, False si no.

        Returns:
            Número de jugadores notificados.
        """
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)

        notified = 0
        for sender in all_senders:
            await sender.send_block_position(x, y, blocked)
            notified += 1

        if notified > 0:
            logger.debug(
                "Broadcast BLOCK_POSITION: pos=(%d,%d) blocked=%s - %d notificados",
                x,
                y,
                blocked,
                notified,
            )

        return notified

    async def broadcast_object_create(self, map_id: int, x: int, y: int, grh_index: int) -> int:
        """Broadcast de OBJECT_CREATE a todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            x: Posición X del objeto.
            y: Posición Y del objeto.
            grh_index: Índice gráfico del objeto.

        Returns:
            Número de jugadores notificados.
        """
        # Obtener todos los jugadores en el mapa
        all_senders = self.map_manager.get_all_message_senders_in_map(map_id)

        notified = 0
        for sender in all_senders:
            await sender.send_object_create(x, y, grh_index)
            notified += 1

        if notified > 0:
            logger.info(
                "Broadcast OBJECT_CREATE: pos=(%d,%d) grh=%d - %d notificados",
                x,
                y,
                grh_index,
                notified,
            )
        else:
            logger.warning(
                "Broadcast OBJECT_CREATE: pos=(%d,%d) grh=%d - 0 jugadores en mapa %d",
                x,
                y,
                grh_index,
                map_id,
            )

        return notified

    async def broadcast_object_delete(self, map_id: int, x: int, y: int) -> None:
        """Envía OBJECT_DELETE a todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
        """
        if not self.map_manager:
            return

        players = self.map_manager.get_all_message_senders_in_map(map_id)
        for message_sender in players:
            await message_sender.send_object_delete(x, y)

    async def broadcast_create_fx(self, map_id: int, char_index: int, fx: int, loops: int) -> None:
        """Envía CREATE_FX a todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            char_index: CharIndex del personaje/NPC.
            fx: ID del efecto visual.
            loops: Número de loops (-1 = infinito, 1 = one-shot).
        """
        if not self.map_manager:
            return

        players = self.map_manager.get_all_message_senders_in_map(map_id)
        notified = 0
        for message_sender in players:
            await message_sender.send_create_fx(char_index, fx, loops)
            notified += 1

        if notified > 0:
            logger.debug(
                "Broadcast CREATE_FX: CharIndex=%d fx=%d loops=%d - %d notificados",
                char_index,
                fx,
                loops,
                notified,
            )
