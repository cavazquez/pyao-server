"""Gestor de mapas y jugadores para broadcast multijugador."""

import asyncio
import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.game.map_manager_spatial import SpatialIndexMixin

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.ground_items_repository import GroundItemsRepository


logger = logging.getLogger(__name__)

# Constantes para rangos de mapas
MAX_MAP_ID = 290
MAX_COORDINATE = 100
MAP_RANGE_1 = 50
MAP_RANGE_2 = 100
MAP_RANGE_3 = 150
MAP_RANGE_4 = 200
MAP_RANGE_5 = 250


class MapManager(SpatialIndexMixin):  # noqa: PLR0904
    """Gestiona qué jugadores y NPCs están en qué mapa para broadcast de eventos."""

    MAX_ITEMS_PER_TILE = 10  # Límite de items por tile

    def __init__(self, ground_items_repo: "GroundItemsRepository | None" = None) -> None:  # noqa: UP037
        """Inicializa el gestor de mapas.

        Args:
            ground_items_repo: Repositorio de ground items (opcional).

        Estructura interna:
        - _players_by_map: {map_id: {user_id: (message_sender, username)}}
        - _npcs_by_map: {map_id: {instance_id: NPC}}
        """
        self._players_by_map: dict[int, dict[int, tuple[MessageSender, str]]] = {}
        self._npcs_by_map: dict[int, dict[str, NPC]] = {}

        # Índice espacial para colisiones
        self._tile_occupation: dict[tuple[int, int, int], str] = {}

        # Tiles bloqueados por mapa (paredes, agua, etc.)
        self._blocked_tiles: dict[int, set[tuple[int, int]]] = {}

        # Puertas cerradas por mapa (bloquean movimiento pero no son "bloqueados" permanentes)
        self._closed_doors: dict[int, set[tuple[int, int]]] = {}

        # Tiles de exit por mapa: {(map_id, x, y): {"to_map": int, "to_x": int, "to_y": int}}
        self._exit_tiles: dict[tuple[int, int, int], dict[str, int]] = {}

        # Tamaños de mapas: {map_id: (width, height)}
        self._map_sizes: dict[int, tuple[int, int]] = {}

        # Ground items: {(map_id, x, y): [Item, Item, ...]}
        self._ground_items: dict[tuple[int, int, int], list[dict[str, int | str | None]]] = {}

        # Repositorio para persistencia
        self.ground_items_repo = ground_items_repo

    def add_player(
        self, map_id: int, user_id: int, message_sender: MessageSender, username: str = ""
    ) -> None:
        """Agrega un jugador a un mapa.

        Args:
            map_id: ID del mapa.
            user_id: ID del usuario.
            message_sender: MessageSender del jugador.
            username: Nombre del usuario (opcional).
        """
        if map_id not in self._players_by_map:
            self._players_by_map[map_id] = {}

        self._players_by_map[map_id][user_id] = (message_sender, username)
        logger.debug("Jugador %d (%s) agregado al mapa %d", user_id, username, map_id)

    def remove_player(self, map_id: int, user_id: int) -> None:
        """Remueve un jugador de un mapa.

        Args:
            map_id: ID del mapa.
            user_id: ID del usuario.
        """
        if map_id in self._players_by_map and user_id in self._players_by_map[map_id]:
            # Limpiar tile occupation para que el tile quede libre
            keys_to_remove = []
            for key, occupant in self._tile_occupation.items():
                if occupant == f"player:{user_id}" and key[0] == map_id:
                    keys_to_remove.append(key)
                    logger.debug(
                        "Tile (%d,%d) liberado al remover jugador %d", key[1], key[2], user_id
                    )

            for key in keys_to_remove:
                del self._tile_occupation[key]

            del self._players_by_map[map_id][user_id]
            logger.debug("Jugador %d removido del mapa %d", user_id, map_id)

            # Limpiar mapa vacío
            if not self._players_by_map[map_id]:
                del self._players_by_map[map_id]
                logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def get_players_in_map(self, map_id: int, exclude_user_id: int | None = None) -> list[int]:
        """Obtiene la lista de user_ids en un mapa.

        Args:
            map_id: ID del mapa.
            exclude_user_id: ID de usuario a excluir (opcional).

        Returns:
            Lista de user_ids en el mapa.
        """
        if map_id not in self._players_by_map:
            return []

        players = list(self._players_by_map[map_id].keys())

        if exclude_user_id is not None and exclude_user_id in players:
            players.remove(exclude_user_id)

        return players

    def get_maps_with_players(self) -> list[int]:
        """Obtiene lista de IDs de mapas que tienen jugadores.

        Returns:
            Lista de map_ids con al menos un jugador.
        """
        return list(self._players_by_map.keys())

    def get_player_message_sender(self, user_id: int) -> MessageSender | None:
        """Get MessageSender for a specific player.

        Args:
            user_id: User ID to search for

        Returns:
            MessageSender if player found online, None otherwise
        """
        for players_dict in self._players_by_map.values():
            if user_id in players_dict:
                message_sender, _ = players_dict[user_id]
                return message_sender
        return None

    def find_player_by_username(self, username: str) -> int | None:
        """Find online player by username (case-insensitive).

        Args:
            username: Username to search for

        Returns:
            user_id if player found online, None otherwise
        """
        username_lower = username.lower().strip()
        for players_dict in self._players_by_map.values():
            for user_id, (_, player_username) in players_dict.items():
                if player_username.lower().strip() == username_lower:
                    return user_id
        return None

    def get_all_online_players(self) -> list[tuple[int, str, int]]:
        """Get list of all online players.

        Returns:
            List of tuples (user_id, username, map_id)
        """
        players = []
        for map_id, players_dict in self._players_by_map.items():
            for user_id, (_, username) in players_dict.items():
                players.append((user_id, username, map_id))
        return players

    def get_player_username(self, user_id: int) -> str | None:
        """Get username for a specific player.

        Args:
            user_id: User ID to search for

        Returns:
            Username if player found online, None otherwise
        """
        for players_dict in self._players_by_map.values():
            if user_id in players_dict:
                _, username = players_dict[user_id]
                return username
        return None

    def get_username(self, user_id: int, map_id: int | None = None) -> str | None:
        """Obtiene el username de un jugador.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa (opcional, si no se provee busca en todos los mapas).

        Returns:
            Username del jugador o None si no existe.
        """
        # Si se especifica un mapa, buscar solo en ese mapa
        if map_id is not None:
            if map_id not in self._players_by_map:
                return None
            player_data = self._players_by_map[map_id].get(user_id)
            return player_data[1] if player_data else None

        # Si no se especifica mapa, buscar en todos los mapas
        for players in self._players_by_map.values():
            if user_id in players:
                return players[user_id][1]

        return None

    def get_message_sender(self, user_id: int, map_id: int | None = None) -> MessageSender | None:
        """Obtiene el MessageSender de un jugador.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa (opcional, si no se provee busca en todos los mapas).

        Returns:
            MessageSender del jugador o None si no existe.
        """
        # Si se especifica un mapa, buscar solo en ese mapa
        if map_id is not None:
            if map_id not in self._players_by_map:
                return None
            player_data = self._players_by_map[map_id].get(user_id)
            return player_data[0] if player_data else None

        # Si no se especifica mapa, buscar en todos los mapas
        for players in self._players_by_map.values():
            if user_id in players:
                return players[user_id][0]

        return None

    def get_all_message_senders_in_map(
        self, map_id: int, exclude_user_id: int | None = None
    ) -> list[MessageSender]:
        """Obtiene todos los MessageSenders de un mapa.

        Args:
            map_id: ID del mapa.
            exclude_user_id: ID de usuario a excluir (opcional).

        Returns:
            Lista de MessageSenders en el mapa.
        """
        if map_id not in self._players_by_map:
            return []

        senders = []
        for user_id, (sender, _username) in self._players_by_map[map_id].items():
            if exclude_user_id is None or user_id != exclude_user_id:
                senders.append(sender)

        return senders

    def get_player_count_in_map(self, map_id: int) -> int:
        """Obtiene el número de jugadores en un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Número de jugadores en el mapa.
        """
        if map_id not in self._players_by_map:
            return 0

        return len(self._players_by_map[map_id])

    def remove_player_from_all_maps(self, user_id: int) -> None:
        """Remueve un jugador de todos los mapas.

        Args:
            user_id: ID del usuario.
        """
        maps_to_clean = []

        for map_id, players in self._players_by_map.items():
            if user_id in players:
                # Limpiar tile occupation para este mapa
                keys_to_remove = []
                for key, occupant in self._tile_occupation.items():
                    if occupant == f"player:{user_id}" and key[0] == map_id:
                        keys_to_remove.append(key)
                        logger.debug(
                            "Tile (%d,%d) liberado al remover jugador %d del mapa %d",
                            key[1],
                            key[2],
                            user_id,
                            map_id,
                        )

                for key in keys_to_remove:
                    del self._tile_occupation[key]

                del players[user_id]
                logger.debug("Jugador %d removido del mapa %d", user_id, map_id)

                if not players:
                    maps_to_clean.append(map_id)

        # Limpiar mapas vacíos
        for map_id in maps_to_clean:
            del self._players_by_map[map_id]
            logger.debug("Mapa %d eliminado (sin jugadores)", map_id)

    def get_all_connected_players(self) -> list[str]:
        """Obtiene la lista de nombres de todos los jugadores conectados.

        Returns:
            Lista de nombres de usuario conectados.
        """
        usernames = []
        for players in self._players_by_map.values():
            for _sender, username in players.values():
                if username and username not in usernames:
                    usernames.append(username)
        return usernames

    def get_all_connected_user_ids(self) -> list[int]:
        """Obtiene la lista de user_ids de todos los jugadores conectados.

        Returns:
            Lista de user_ids conectados.
        """
        user_ids = []
        for players in self._players_by_map.values():
            for user_id in players:
                if user_id not in user_ids:
                    user_ids.append(user_id)
        return user_ids

    # Métodos para NPCs
    def add_npc(self, map_id: int, npc: NPC) -> None:
        """Agrega un NPC a un mapa.

        Args:
            map_id: ID del mapa.
            npc: Instancia del NPC.

        Raises:
            ValueError: Si el tile ya está ocupado por otro NPC o jugador.
        """
        if map_id not in self._npcs_by_map:
            self._npcs_by_map[map_id] = {}

        # Verificar que el tile no esté ocupado
        tile_key = (map_id, npc.x, npc.y)
        if tile_key in self._tile_occupation:
            occupant = self._tile_occupation[tile_key]
            msg = (
                f"No se puede agregar NPC {npc.name} en ({npc.x},{npc.y}): "
                f"tile ya ocupado por {occupant}"
            )
            raise ValueError(msg)

        self._npcs_by_map[map_id][npc.instance_id] = npc

        # Marcar tile como ocupado en el índice espacial
        self._tile_occupation[tile_key] = f"npc:{npc.instance_id}"

        logger.debug("NPC %s agregado al mapa %d en tile (%d,%d)", npc.name, map_id, npc.x, npc.y)

    def move_npc(
        self, map_id: int, char_index: int, old_x: int, old_y: int, new_x: int, new_y: int
    ) -> None:
        """Mueve un NPC de una posición a otra.

        Args:
            map_id: ID del mapa.
            char_index: CharIndex del NPC.
            old_x: Posición X anterior.
            old_y: Posición Y anterior.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
        """
        # Liberar tile anterior
        old_tile_key = (map_id, old_x, old_y)
        if old_tile_key in self._tile_occupation:
            del self._tile_occupation[old_tile_key]

        # Buscar el NPC por char_index
        if map_id in self._npcs_by_map:
            for npc in self._npcs_by_map[map_id].values():
                if npc.char_index == char_index:
                    # Ocupar nuevo tile
                    new_tile_key = (map_id, new_x, new_y)
                    self._tile_occupation[new_tile_key] = f"npc:{npc.instance_id}"
                    break

    def remove_npc(self, map_id: int, instance_id: str) -> None:
        """Remueve un NPC de un mapa.

        Args:
            map_id: ID del mapa.
            instance_id: ID único de la instancia del NPC.
        """
        if map_id in self._npcs_by_map and instance_id in self._npcs_by_map[map_id]:
            npc = self._npcs_by_map[map_id][instance_id]
            npc_name = npc.name

            # Limpiar tile occupation para que el tile quede libre
            tile_key = (map_id, npc.x, npc.y)
            if tile_key in self._tile_occupation:
                del self._tile_occupation[tile_key]
                logger.debug("Tile (%d,%d) liberado al remover NPC %s", npc.x, npc.y, npc_name)

            del self._npcs_by_map[map_id][instance_id]
            logger.debug("NPC %s removido del mapa %d", npc_name, map_id)

            # Limpiar mapa vacío
            if not self._npcs_by_map[map_id]:
                del self._npcs_by_map[map_id]
                logger.debug("Mapa %d eliminado (sin NPCs)", map_id)

    def get_npcs_in_map(self, map_id: int) -> list[NPC]:
        """Obtiene todos los NPCs de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Lista de NPCs en el mapa.
        """
        if map_id not in self._npcs_by_map:
            return []

        return list(self._npcs_by_map[map_id].values())

    def get_all_npcs(self) -> list[NPC]:
        """Obtiene todos los NPCs de todos los mapas.

        Returns:
            Lista de todos los NPCs.
        """
        all_npcs: list[NPC] = []
        for npcs_in_map in self._npcs_by_map.values():
            all_npcs.extend(npcs_in_map.values())
        return all_npcs

    def get_npc_by_char_index(self, map_id: int, char_index: int) -> NPC | None:
        """Obtiene un NPC por su CharIndex en un mapa.

        Args:
            map_id: ID del mapa.
            char_index: CharIndex del NPC.

        Returns:
            Instancia del NPC o None si no existe.
        """
        if map_id not in self._npcs_by_map:
            return None

        for npc in self._npcs_by_map[map_id].values():
            if npc.char_index == char_index:
                return npc

        return None

    # Ground Items Methods

    def add_ground_item(
        self, map_id: int, x: int, y: int, item: dict[str, int | str | None]
    ) -> None:
        """Agrega un item al suelo en una posición específica.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            item: Diccionario con datos del item:
                - item_id: ID del item
                - quantity: Cantidad
                - grh_index: Índice gráfico
                - owner_id (opcional): Dueño temporal
                - spawn_time (opcional): Timestamp de spawn
        """
        key = (map_id, x, y)
        if key not in self._ground_items:
            self._ground_items[key] = []

        # Límite de items por tile
        if len(self._ground_items[key]) >= self.MAX_ITEMS_PER_TILE:
            logger.warning(
                "Tile (%d, %d) en mapa %d tiene 10 items, no se puede agregar más", x, y, map_id
            )
            return

        self._ground_items[key].append(item)
        logger.debug(
            "Item agregado al suelo: mapa=%d pos=(%d,%d) item_id=%d cantidad=%d",
            map_id,
            x,
            y,
            item.get("item_id"),
            item.get("quantity"),
        )

        # Persistir en Redis de forma asíncrona (fire and forget)
        if self.ground_items_repo:
            task = asyncio.create_task(self._persist_ground_items(map_id))
            # Guardar referencia para evitar warning
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    def get_ground_items(self, map_id: int, x: int, y: int) -> list[dict[str, int | str | None]]:
        """Obtiene todos los items en un tile específico.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Lista de items en ese tile (vacía si no hay items).
        """
        key = (map_id, x, y)
        return self._ground_items.get(key, [])

    def remove_ground_item(
        self, map_id: int, x: int, y: int, item_index: int = 0
    ) -> dict[str, int | str | None] | None:
        """Remueve un item del suelo.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            item_index: Índice del item en la lista (default: 0, primer item).

        Returns:
            Item removido o None si no existe.
        """
        key = (map_id, x, y)
        if key not in self._ground_items:
            return None

        items = self._ground_items[key]
        if item_index >= len(items):
            logger.warning(
                "Intento de remover item_index=%d pero solo hay %d items en (%d,%d)",
                item_index,
                len(items),
                x,
                y,
            )
            return None

        item = items.pop(item_index)

        # Limpiar si no quedan items
        if not items:
            del self._ground_items[key]

        logger.debug(
            "Item removido del suelo: mapa=%d pos=(%d,%d) item_id=%d",
            map_id,
            x,
            y,
            item.get("item_id"),
        )

        # Persistir en Redis
        if self.ground_items_repo:
            task = asyncio.create_task(self._persist_ground_items(map_id))
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

        return item

    def clear_ground_items(self, map_id: int) -> int:
        """Limpia todos los items de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Cantidad de items removidos.
        """
        keys_to_remove = [key for key in self._ground_items if key[0] == map_id]

        total_items = sum(len(self._ground_items[key]) for key in keys_to_remove)

        for key in keys_to_remove:
            del self._ground_items[key]

        if total_items > 0:
            logger.info("Limpiados %d items del mapa %d", total_items, map_id)

        return total_items

    def get_ground_items_count(self, map_id: int) -> int:
        """Obtiene la cantidad total de items en el suelo de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Cantidad de items.
        """
        return sum(len(items) for key, items in self._ground_items.items() if key[0] == map_id)

    async def _persist_ground_items(self, map_id: int) -> None:
        """Persiste los ground items de un mapa en Redis.

        Args:
            map_id: ID del mapa.
        """
        if not self.ground_items_repo:
            return

        # Filtrar items del mapa
        map_items: dict[tuple[int, int], list[dict[str, int | str | None]]] = {}
        for (item_map_id, x, y), items in self._ground_items.items():
            if item_map_id == map_id:
                map_items[x, y] = items

        # Guardar en Redis
        await self.ground_items_repo.save_ground_items(map_id, map_items)

    async def load_ground_items(self, map_id: int) -> None:
        """Carga los ground items de un mapa desde Redis.

        Args:
            map_id: ID del mapa.
        """
        if not self.ground_items_repo:
            return

        # Cargar desde Redis
        map_items = await self.ground_items_repo.load_ground_items(map_id)

        # Agregar a memoria
        for (x, y), items in map_items.items():
            key = (map_id, x, y)
            self._ground_items[key] = items

        if map_items:
            total_items = sum(len(items) for items in map_items.values())
            logger.info("Cargados %d items del mapa %d desde Redis", total_items, map_id)

    @staticmethod
    def _load_metadata_file(metadata_path: Path) -> tuple[int, int, list[dict[str, object]] | None]:
        """Lee el archivo de metadatos devolviendo tamaño y bloqueados embebidos.

        Returns:
            tuple[int, int, list[dict[str, object]] | None]: width, height y bloqueados opcionales.
        """
        width = 100
        height = 100
        blocked_tiles: list[dict[str, object]] | None = None

        if metadata_path.exists():  # noqa: PLR1702
            with metadata_path.open("r", encoding="utf-8") as f:
                try:
                    # Intentar leer como JSON único primero
                    metadata = json.load(f)

                    # Si es una lista, buscar el mapa correcto
                    if isinstance(metadata, list):
                        # Para NDJSON con múltiples mapas, usar el primero por ahora
                        if len(metadata) > 0:
                            first_map = metadata[0]
                            width = int(first_map.get("w", width))
                            height = int(first_map.get("h", height))
                    else:
                        # JSON único tradicional
                        width = int(metadata.get("w", metadata.get("width", width)))
                        height = int(metadata.get("h", metadata.get("height", height)))

                    if "blocked_tiles" in metadata:
                        raw_blocked = metadata.get("blocked_tiles")
                        if isinstance(raw_blocked, list):
                            blocked_tiles = [tile for tile in raw_blocked if isinstance(tile, dict)]
                        else:
                            blocked_tiles = []

                except json.JSONDecodeError:
                    # Si falla, intentar como NDJSON
                    f.seek(0)
                    maps_metadata = []
                    for line_number, line in enumerate(f, start=1):
                        stripped = line.strip()
                        if not stripped:
                            continue
                        try:
                            parsed_line = json.loads(stripped)
                            if isinstance(parsed_line, dict):
                                maps_metadata.append(parsed_line)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Formato inválido en %s línea %d: %s",
                                metadata_path,
                                line_number,
                                stripped[:100],
                            )
                            continue

                    # Usar el primer mapa encontrado
                    if maps_metadata:
                        first_map = maps_metadata[0]
                        width = int(first_map.get("w", width))
                        height = int(first_map.get("h", height))
        else:
            logger.warning("Metadata de mapa no encontrada: %s", metadata_path)

        return width, height, blocked_tiles

    @staticmethod
    def _load_blocked_file(blocked_path: Path) -> list[dict[str, object]] | None:
        """Obtiene los tiles bloqueados desde un archivo dedicado.

        Returns:
            list[dict[str, object]] | None: Lista de tiles o None si falta el archivo.
        """
        if not blocked_path.exists():
            logger.warning("Archivo de tiles bloqueados no encontrado: %s", blocked_path)
            return None

        with blocked_path.open("r", encoding="utf-8") as f:
            try:
                raw_blocked = json.load(f)
            except json.JSONDecodeError:
                f.seek(0)
                ndjson_tiles: list[dict[str, object]] = []
                for line_number, line in enumerate(f, start=1):
                    stripped = line.strip()
                    if not stripped:
                        continue
                    try:
                        parsed_line = json.loads(stripped)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Formato inválido en %s línea %d: %s",
                            blocked_path,
                            line_number,
                            stripped[:100],
                        )
                        continue
                    if isinstance(parsed_line, dict):
                        ndjson_tiles.append(parsed_line)
                raw_blocked = ndjson_tiles

        if isinstance(raw_blocked, list):
            return [tile for tile in raw_blocked if isinstance(tile, dict)]

        return []

    def _load_map_transitions(self, map_id: int, transitions_path: Path) -> None:
        """Carga transiciones de mapa desde un archivo JSON.

        Args:
            map_id: ID del mapa actual.
            transitions_path: Ruta al archivo de transiciones.
        """
        if not transitions_path.exists():
            logger.debug("Archivo de transiciones no encontrado: %s", transitions_path)
            return

        try:
            with transitions_path.open("r", encoding="utf-8") as f:
                data = json.load(f)

            logger.debug("Cargando transiciones para mapa %d desde %s", map_id, transitions_path)

            transitions_loaded = 0
            for transition_group in data.get("transitions", []):
                if transition_group.get("from_map") != map_id:
                    continue

                logger.debug("Encontrado grupo de transiciones para mapa %d", map_id)

                for exit_data in transition_group.get("exits", []):
                    x = self._coerce_int(exit_data.get("x"))
                    y = self._coerce_int(exit_data.get("y"))
                    to_map = self._coerce_int(exit_data.get("to_map"))
                    to_x = self._coerce_int(exit_data.get("to_x"))
                    to_y = self._coerce_int(exit_data.get("to_y"))

                    if (
                        x is not None
                        and y is not None
                        and to_map
                        and to_x is not None
                        and to_y is not None
                    ):
                        # Filtrar solo transiciones válidas (mapas entre 1-290)
                        if (
                            1 <= to_map <= MAX_MAP_ID
                            and 1 <= to_x <= MAX_COORDINATE
                            and 1 <= to_y <= MAX_COORDINATE
                        ):
                            self._exit_tiles[map_id, x, y] = {
                                "to_map": to_map,
                                "to_x": to_x,
                                "to_y": to_y,
                            }
                            transitions_loaded += 1
                            logger.debug(
                                "Transición cargada: Mapa %d (%d,%d) -> Mapa %d (%d,%d)",
                                map_id,
                                x,
                                y,
                                to_map,
                                to_x,
                                to_y,
                            )
                        else:
                            logger.debug(
                                "Transición inválida ignorada: Mapa %d (%d,%d) -> Mapa %d (%d,%d)",
                                map_id,
                                x,
                                y,
                                to_map,
                                to_x,
                                to_y,
                            )

            logger.info("Transiciones cargadas para mapa %d: %d", map_id, transitions_loaded)

        except (OSError, json.JSONDecodeError):
            logger.warning("No se pudieron cargar transiciones desde %s", transitions_path)

    @staticmethod
    def _build_blocked_data(
        map_id: int, blocked_tiles: list[dict[str, object]]
    ) -> tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
        """Procesa tiles bloqueados generando sets y salidas.

        Returns:
            tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
                Conjunto de tiles bloqueados, cantidad de exits y mapping de exits.
        """
        blocked_set: set[tuple[int, int]] = set()
        exit_tiles: dict[tuple[int, int, int], dict[str, int]] = {}
        exit_count = 0

        for tile in blocked_tiles:
            raw_x = tile.get("x")
            raw_y = tile.get("y")
            tile_type = tile.get(
                "t", tile.get("type")
            )  # "t" para formato JSON, "type" como fallback

            x = MapManager._coerce_int(raw_x)
            y = MapManager._coerce_int(raw_y)
            if x is None or y is None:
                continue

            if tile_type == "exit":
                to_map_raw = tile.get("to_map")
                to_x_raw = tile.get("to_x")
                to_y_raw = tile.get("to_y")

                to_map = MapManager._coerce_int(to_map_raw)
                to_x = MapManager._coerce_int(to_x_raw)
                to_y = MapManager._coerce_int(to_y_raw)

                if to_map and to_x is not None and to_y is not None and to_map > 0:
                    exit_tiles[map_id, x, y] = {
                        "to_map": to_map,
                        "to_x": to_x,
                        "to_y": to_y,
                    }
                    exit_count += 1
                    logger.debug(
                        "Exit tile en mapa %d (%d,%d) -> mapa %d (%d,%d)",
                        map_id,
                        x,
                        y,
                        to_map,
                        to_x,
                        to_y,
                    )

            blocked_set.add((x, y))

        return blocked_set, exit_count, exit_tiles

    def load_map_data(self, map_id: int, map_file_path: str | Path) -> None:
        """Carga metadatos y tiles bloqueados de un mapa.

        Args:
            map_id: ID del mapa.
            map_file_path: Ruta al archivo *_metadata.json del mapa.
        """
        metadata_path = Path(map_file_path)
        # El nombre del archivo es como "metadata_001-064.json"
        # Extraer el rango para buscar "blocked_001-050.json" (los rangos no coinciden)
        stem = metadata_path.stem
        if "_" in stem:
            _, range_part = stem.split("_", 1)
            # Para el mapa 1, el rango en metadata es 001-064 pero en blocked es 001-050
            if map_id <= MAP_RANGE_1:
                blocked_path = metadata_path.with_name("blocked_001-050.json")
            elif map_id <= MAP_RANGE_2:
                blocked_path = metadata_path.with_name("blocked_051-100.json")
            elif map_id <= MAP_RANGE_3:
                blocked_path = metadata_path.with_name("blocked_101-150.json")
            elif map_id <= MAP_RANGE_4:
                blocked_path = metadata_path.with_name("blocked_151-200.json")
            else:
                blocked_path = metadata_path.with_name(f"blocked_{range_part}.json")
        else:
            # Fallback para formato sin rango
            blocked_path = metadata_path.with_name("blocked.json")

        try:
            width, height, blocked_tiles = self._load_metadata_file(metadata_path)
            self._map_sizes[map_id] = (width, height)

            if blocked_tiles is None:
                blocked_tiles = self._load_blocked_file(blocked_path)
                if blocked_tiles is None:
                    self._blocked_tiles[map_id] = set()
                    return

            blocked_set, exit_count, exit_tiles = self._build_blocked_data(map_id, blocked_tiles)
            self._exit_tiles.update(exit_tiles)

            self._blocked_tiles[map_id] = blocked_set

            # Cargar transiciones adicionales desde archivo separado
            # Determinar el rango del archivo de transiciones
            if map_id <= MAP_RANGE_1:
                transitions_file = "transitions_001-050.json"
            elif map_id <= MAP_RANGE_2:
                transitions_file = "transitions_051-100.json"
            elif map_id <= MAP_RANGE_3:
                transitions_file = "transitions_101-150.json"
            elif map_id <= MAP_RANGE_4:
                transitions_file = "transitions_151-200.json"
            elif map_id <= MAP_RANGE_5:
                transitions_file = "transitions_201-250.json"
            else:
                transitions_file = "transitions_251-290.json"

            self._load_map_transitions(map_id, metadata_path.parent / transitions_file)

            logger.info(
                "Mapa %d cargado: %dx%d, %d tiles bloqueados, %d exits",
                map_id,
                width,
                height,
                len(blocked_set),
                exit_count,
            )

        except (OSError, json.JSONDecodeError):
            logger.exception("Error cargando mapa %d", map_id)
            self._map_sizes[map_id] = (width, height)

    @staticmethod
    def _coerce_int(value: object) -> int | None:
        """Convierte un valor a int devolviendo None si no es posible.

        Returns:
            int | None: El entero convertido o None si no se pudo convertir.
        """
        if isinstance(value, bool) or value is None:
            return None

        if isinstance(value, (int, float)):
            return int(value)

        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            try:
                return int(value)
            except ValueError:
                return None

        return None

    def get_map_size(self, map_id: int) -> tuple[int, int]:
        """Obtiene el tamaño de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Tupla (width, height). Si el mapa no está cargado, retorna (100, 100).
        """
        return self._map_sizes.get(map_id, (100, 100))

    def get_exit_tile(self, map_id: int, x: int, y: int) -> dict[str, int] | None:
        """Verifica si una posición es un tile de exit y retorna su destino.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            Dict con {to_map, to_x, to_y} si es un exit, None si no.
        """
        return self._exit_tiles.get((map_id, x, y))

    def block_tile(self, map_id: int, x: int, y: int) -> None:
        """Marca una puerta como cerrada (bloquea movimiento pero no es un tile "bloqueado").

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
        """
        if map_id not in self._closed_doors:
            self._closed_doors[map_id] = set()

        self._closed_doors[map_id].add((x, y))
        logger.info(
            "🚪 PUERTA CERRADA: Mapa %d (%d, %d) - Total puertas cerradas: %d",
            map_id,
            x,
            y,
            len(self._closed_doors.get(map_id, set())),
        )

    def unblock_tile(self, map_id: int, x: int, y: int) -> None:
        """Marca una puerta como abierta (permite movimiento).

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
        """
        if map_id in self._closed_doors:
            self._closed_doors[map_id].discard((x, y))
            logger.info(
                "🚪 PUERTA ABIERTA: Mapa %d (%d, %d) - Total puertas cerradas: %d",
                map_id,
                x,
                y,
                len(self._closed_doors.get(map_id, set())),
            )

    def is_door_closed(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si hay una puerta cerrada en una posición.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si hay una puerta cerrada, False en caso contrario.
        """
        if map_id not in self._closed_doors:
            return False
        return (x, y) in self._closed_doors[map_id]
