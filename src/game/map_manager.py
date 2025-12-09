"""Gestor de mapas y jugadores para broadcast multijugador."""

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.game.map_manager_spatial import SpatialIndexMixin
from src.game.map_metadata_loader import MapMetadataLoader
from src.game.npc_index import NpcIndex

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


class MapManager(SpatialIndexMixin):
    """Gestiona qué jugadores y NPCs están en qué mapa para broadcast de eventos."""

    MAX_ITEMS_PER_TILE = 10  # Límite de items por tile

    def __init__(self, ground_items_repo: "GroundItemsRepository | None" = None) -> None:  # noqa: UP037
        """Inicializa el gestor de mapas.

        Args:
            ground_items_repo: Repositorio de ground items (opcional).

        Estructura interna:
        - _players_by_map: {map_id: {user_id: (message_sender, username)}}
        - _npcs_by_map: {map_id: {instance_id: NPC}} (delegado en NpcIndex)
        """
        self._players_by_map: dict[int, dict[int, tuple[MessageSender, str]]] = {}

        # Índice espacial para colisiones
        self._tile_occupation: dict[tuple[int, int, int], str] = {}

        # Índice de NPCs (mantiene compatibilidad con _npcs_by_map)
        self._npc_index = NpcIndex(self._tile_occupation)
        self._npcs_by_map = self._npc_index.npcs_by_map

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

        # Loader de metadatos (blocked, exits, tamaños)
        self._metadata_loader = MapMetadataLoader(
            map_ranges=(MAP_RANGE_1, MAP_RANGE_2, MAP_RANGE_3, MAP_RANGE_4, MAP_RANGE_5),
            max_map_id=MAX_MAP_ID,
            max_coordinate=MAX_COORDINATE,
        )

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

        """
        self._npc_index.add_npc(map_id, npc)

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
        self._npc_index.move_npc(map_id, char_index, old_x, old_y, new_x, new_y)

    def remove_npc(self, map_id: int, instance_id: str) -> None:
        """Remueve un NPC de un mapa.

        Args:
            map_id: ID del mapa.
            instance_id: ID único de la instancia del NPC.
        """
        self._npc_index.remove_npc(map_id, instance_id)

    def get_npcs_in_map(self, map_id: int) -> list[NPC]:
        """Obtiene todos los NPCs de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Lista de NPCs en el mapa.
        """
        return list(self._npc_index.get_npcs_in_map(map_id))

    def get_all_npcs(self) -> list[NPC]:
        """Obtiene todos los NPCs de todos los mapas.

        Returns:
            Lista de todos los NPCs.
        """
        return list(self._npc_index.get_all_npcs())

    def get_npc_by_char_index(self, map_id: int, char_index: int) -> NPC | None:
        """Obtiene un NPC por su CharIndex en un mapa.

        Args:
            map_id: ID del mapa.
            char_index: CharIndex del NPC.

        Returns:
            Instancia del NPC o None si no existe.
        """
        result = self._npc_index.get_npc_by_char_index(map_id, char_index)
        return result if result is not None else None

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

    def load_map_data(self, map_id: int, map_file_path: str | Path) -> None:
        """Carga metadatos y tiles bloqueados de un mapa delegando en el loader."""
        result = self._metadata_loader.load_map_data(map_id, map_file_path)
        self._map_sizes[map_id] = (result.width, result.height)
        self._blocked_tiles[map_id] = result.blocked_tiles
        self._exit_tiles.update(result.exit_tiles)

        logger.info(
            "Mapa %d cargado: %dx%d, %d tiles bloqueados, %d exits",
            map_id,
            result.width,
            result.height,
            len(result.blocked_tiles),
            result.exit_count,
        )

    # Métodos de compatibilidad/soporte para tests existentes
    @staticmethod
    def _load_metadata_file(metadata_path: Path) -> tuple[int, int, list[dict[str, object]] | None]:
        return MapMetadataLoader.load_metadata_file_static(metadata_path)

    @staticmethod
    def _load_blocked_file(blocked_path: Path) -> list[dict[str, object]] | None:
        return MapMetadataLoader.load_blocked_file_static(blocked_path)

    def _get_blocked_tiles_for_map(
        self, map_id: int, blocked_path: Path
    ) -> list[dict[str, object]] | None:
        return self._metadata_loader.get_blocked_tiles_for_map(map_id, blocked_path)

    def _load_map_transitions(self, map_id: int, transitions_path: Path) -> None:
        self._metadata_loader.load_map_transitions(map_id, transitions_path, self._exit_tiles)

    @staticmethod
    def _build_blocked_data(
        map_id: int, blocked_tiles: list[dict[str, object]]
    ) -> tuple[set[tuple[int, int]], int, dict[tuple[int, int, int], dict[str, int]]]:
        return MapMetadataLoader.build_blocked_data(map_id, blocked_tiles)

    @staticmethod
    def _coerce_int(value: object) -> int | None:
        return MapMetadataLoader.coerce_int(value)

    @property
    def _missing_transitions_files(self) -> set[Path]:
        return self._metadata_loader.missing_transitions_files

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
