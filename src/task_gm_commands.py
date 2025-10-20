"""Tarea para manejar comandos de Game Master (GM)."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.packet_validator import PacketValidator
from src.task import Task

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskGMCommands(Task):
    """Tarea que maneja comandos de Game Master."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        map_manager: MapManager | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de comandos GM.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast multijugador.
            session_data: Datos de sesión compartidos (opcional).
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.session_data = session_data

    def _parse_packet(self) -> tuple[int, str, int, int, int] | None:
        """Parsea y valida el paquete de comando GM (teletransporte).

        El formato esperado es:
        - Byte 0: PacketID (GM_COMMANDS = 122)
        - Byte 1: Subcomando GM (ej: WARP_CHAR)
        - String: Username (UTF-16LE con length prefix)
        - Int16: Map ID
        - Byte: X
        - Byte: Y

        Returns:
            Tupla (subcommand, username, map_id, x, y) o None si hay error.
        """
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        result = validator.validate_gm_teleport()

        if validator.has_errors():
            logger.warning("Error validando GM_COMMANDS: %s", validator.get_error_message())
            return None

        return result

    async def execute(self) -> None:
        """Ejecuta el comando GM de teletransporte."""
        # Parsear parámetros
        parsed = self._parse_packet()
        if parsed is None:
            logger.warning(
                "Paquete GM_COMMANDS inválido desde %s",
                self.message_sender.connection.address,
            )
            return

        subcommand, username, map_id, x, y = parsed

        logger.info(
            "Comando GM recibido: subcommand=%d, username=%s, map=%d, pos=(%d,%d)",
            subcommand,
            username,
            map_id,
            x,
            y,
        )

        # Verificar que el player_repo esté disponible
        if self.player_repo is None:
            logger.error("PlayerRepository no está disponible para comando GM")
            return

        # Obtener user_id de la sesión
        if self.session_data is None or "user_id" not in self.session_data:
            logger.warning(
                "Intento de comando GM sin user_id en sesión desde %s",
                self.message_sender.connection.address,
            )
            return

        user_id_value = self.session_data["user_id"]
        if isinstance(user_id_value, dict):
            logger.error("user_id en sesión es un dict, esperaba int")
            return

        user_id = int(user_id_value)

        # Debug: mostrar bytes del username
        logger.debug(
            "Username recibido: '%s' (bytes: %s)",
            username,
            username.encode("utf-8").hex() if username else "empty",
        )

        # Si el username es "YO" o está vacío, teletransportar al propio jugador
        # El cliente Godot envía "YO" pero puede llegar con encoding diferente
        if not username or username.upper() == "YO" or username == "余":
            await self._teleport_player(user_id, map_id, x, y)
        else:
            # TODO: Implementar teletransporte de otros jugadores (requiere buscar por username)
            await self.message_sender.send_console_msg(
                "Teletransporte de otros jugadores no implementado aún."
            )
            logger.info("Teletransporte de otros jugadores no implementado: %s", username)

    async def _teleport_player(self, user_id: int, new_map: int, new_x: int, new_y: int) -> None:
        """Teletransporta un jugador a una nueva posición.

        Args:
            user_id: ID del jugador.
            new_map: ID del nuevo mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
        """
        from src.account_repository import AccountRepository  # noqa: PLC0415

        if not self.player_repo or not self.map_manager:
            return

        # Obtener posición actual
        position = await self.player_repo.get_position(user_id)
        if position is None:
            logger.warning("No se encontró posición para user_id %d", user_id)
            return

        current_map = position["map"]
        current_x = position["x"]
        current_y = position["y"]
        current_heading = position.get("heading", 3)

        # Si es el mismo mapa, solo actualizar posición
        if current_map == new_map:
            # Actualizar posición en Redis
            await self.player_repo.set_position(user_id, new_x, new_y, new_map, current_heading)

            # Actualizar índice espacial
            self.map_manager.update_player_tile(
                user_id, current_map, current_x, current_y, new_x, new_y
            )

            # Enviar POS_UPDATE
            await self.message_sender.send_pos_update(new_x, new_y)

            # Broadcast CHARACTER_REMOVE en posición anterior
            if self.broadcast_service:
                await self.broadcast_service.broadcast_character_remove(current_map, user_id)

            # Broadcast CHARACTER_CREATE en nueva posición
            if self.broadcast_service:
                account_repo = AccountRepository(self.player_repo.redis)
                account_data = await account_repo.get_account_by_user_id(user_id)

                char_body = 1
                char_head = 1
                username_str = f"Player{user_id}"

                if account_data:
                    char_body = int(account_data.get("char_race", 1))
                    char_head = int(account_data.get("char_head", 1))
                    username_str = account_data.get("username", f"Player{user_id}")
                    if char_body == 0:
                        char_body = 1

                await self.broadcast_service.broadcast_character_create(
                    map_id=new_map,
                    char_index=user_id,
                    body=char_body,
                    head=char_head,
                    heading=current_heading,
                    x=new_x,
                    y=new_y,
                    name=username_str,
                )

            logger.info(
                "User %d teletransportado en mismo mapa %d: (%d,%d) -> (%d,%d)",
                user_id,
                current_map,
                current_x,
                current_y,
                new_x,
                new_y,
            )
        else:
            # Cambio de mapa - usar la misma lógica que task_walk
            await self._teleport_to_different_map(
                user_id, current_map, current_x, current_y, current_heading, new_map, new_x, new_y
            )

    async def _teleport_to_different_map(  # noqa: PLR0915
        self,
        user_id: int,
        current_map: int,
        current_x: int,
        current_y: int,
        heading: int,
        new_map: int,
        new_x: int,
        new_y: int,
    ) -> None:
        """Teletransporta un jugador a un mapa diferente.

        Args:
            user_id: ID del jugador.
            current_map: ID del mapa actual.
            current_x: Posición X actual.
            current_y: Posición Y actual.
            heading: Dirección actual.
            new_map: ID del nuevo mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
        """
        import asyncio  # noqa: PLC0415

        from src.account_repository import AccountRepository  # noqa: PLC0415

        if not self.player_repo or not self.map_manager:
            return

        # 1. Enviar CHANGE_MAP
        await self.message_sender.send_change_map(new_map)

        # 2. Delay para que el cliente cargue el mapa
        await asyncio.sleep(0.1)

        # 3. Actualizar posición en Redis
        await self.player_repo.set_position(user_id, new_x, new_y, new_map, heading)

        # 4. Enviar POS_UPDATE
        await self.message_sender.send_pos_update(new_x, new_y)

        # 5. Remover jugador del mapa anterior
        self.map_manager.remove_player(current_map, user_id)

        # 6. Broadcast CHARACTER_REMOVE en mapa anterior
        if self.broadcast_service:
            await self.broadcast_service.broadcast_character_remove(current_map, user_id)

        # 7. Agregar jugador al nuevo mapa
        account_repo = AccountRepository(self.player_repo.redis)
        account_data = await account_repo.get_account_by_user_id(user_id)
        username = (
            account_data.get("username", f"Player{user_id}") if account_data else f"Player{user_id}"
        )
        self.map_manager.add_player(new_map, user_id, self.message_sender, username)

        # 8. Enviar CHARACTER_CREATE del propio jugador
        char_body = 1
        char_head = 1

        if account_data:
            char_body = int(account_data.get("char_race", 1))
            char_head = int(account_data.get("char_head", 1))
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
        existing_players = self.map_manager.get_players_in_map(new_map)
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

        # 11. Enviar todos los objetos del suelo
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
            logger.info("Enviados %d ground items en teletransporte a mapa %d", items_sent, new_map)

        # 12. Broadcast CHARACTER_CREATE a otros jugadores en el nuevo mapa
        if self.broadcast_service:
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
            "User %d teletransportado: mapa %d -> %d, pos (%d,%d) -> (%d,%d)",
            user_id,
            current_map,
            new_map,
            current_x,
            current_y,
            new_x,
            new_y,
        )
