"""Gestor de mapas y jugadores para broadcast multijugador."""

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from src.game.door_state import DoorState
from src.game.exit_index import ExitIndex
from src.game.ground_item_index import GroundItemIndex
from src.game.map_manager_spatial import SpatialIndexMixin
from src.game.map_metadata_loader import MapMetadataLoader
from src.game.npc_index import NpcIndex
from src.game.player_index import PlayerIndex
from src.game.tile_occupation import TileOccupation

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
        - _players_by_map: {map_id: {user_id: (message_sender, username)}} (delegado en PlayerIndex)
        - _npcs_by_map: {map_id: {instance_id: NPC}} (delegado en NpcIndex)
        """
        # Índice espacial para colisiones
        self._tile_occupation_store = TileOccupation()
        self._tile_occupation: dict[tuple[int, int, int], str] = self._tile_occupation_store.data

        # Índice de jugadores (mantiene compatibilidad con _players_by_map)
        self._player_index = PlayerIndex(self._tile_occupation_store)
        self._players_by_map = self._player_index.players_by_map

        # Índice de NPCs (mantiene compatibilidad con _npcs_by_map)
        self._npc_index = NpcIndex(self._tile_occupation_store)
        self._npcs_by_map = self._npc_index.npcs_by_map

        # Tiles bloqueados por mapa (paredes, agua, etc.)
        self._blocked_tiles: dict[int, set[tuple[int, int]]] = {}

        # Puertas cerradas
        self._door_state = DoorState()
        self._closed_doors = self._door_state.data

        # Exits
        self._exit_index = ExitIndex()
        self._exit_tiles = self._exit_index.data

        # Tamaños de mapas: {map_id: (width, height)}
        self._map_sizes: dict[int, tuple[int, int]] = {}

        # Ground items index (compatibilidad con _ground_items)
        self._ground_items_repo = ground_items_repo
        self._ground_index = GroundItemIndex(self.MAX_ITEMS_PER_TILE, ground_items_repo)
        self._ground_items = self._ground_index.ground_items

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
        self._player_index.add_player(map_id, user_id, message_sender, username)

    def remove_player(self, map_id: int, user_id: int) -> None:
        """Remueve un jugador de un mapa.

        Args:
            map_id: ID del mapa.
            user_id: ID del usuario.
        """
        self._player_index.remove_player(map_id, user_id)

    def get_players_in_map(self, map_id: int, exclude_user_id: int | None = None) -> list[int]:
        """Obtiene la lista de user_ids en un mapa.

        Args:
            map_id: ID del mapa.
            exclude_user_id: ID de usuario a excluir (opcional).

        Returns:
            Lista de user_ids en el mapa.
        """
        return self._player_index.get_players_in_map(map_id, exclude_user_id)

    def get_maps_with_players(self) -> list[int]:
        """Obtiene lista de IDs de mapas que tienen jugadores.

        Returns:
            Lista de map_ids con al menos un jugador.
        """
        return self._player_index.get_maps_with_players()

    def get_player_message_sender(self, user_id: int) -> MessageSender | None:
        """Get MessageSender for a specific player.

        Args:
            user_id: User ID to search for

        Returns:
            MessageSender if player found online, None otherwise
        """
        return self._player_index.get_player_message_sender(user_id)

    def find_player_by_username(self, username: str) -> int | None:
        """Find online player by username (case-insensitive).

        Args:
            username: Username to search for

        Returns:
            user_id if player found online, None otherwise
        """
        return self._player_index.find_player_by_username(username)

    def get_all_online_players(self) -> list[tuple[int, str, int]]:
        """Get list of all online players.

        Returns:
            List of tuples (user_id, username, map_id)
        """
        return self._player_index.get_all_online_players()

    def get_player_username(self, user_id: int) -> str | None:
        """Get username for a specific player.

        Args:
            user_id: User ID to search for

        Returns:
            Username if player found online, None otherwise
        """
        return self._player_index.get_player_username(user_id)

    def get_username(self, user_id: int, map_id: int | None = None) -> str | None:
        """Obtiene el username de un jugador.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa (opcional, si no se provee busca en todos los mapas).

        Returns:
            Username del jugador o None si no existe.
        """
        return self._player_index.get_username(user_id, map_id)

    def get_message_sender(self, user_id: int, map_id: int | None = None) -> MessageSender | None:
        """Obtiene el MessageSender de un jugador.

        Args:
            user_id: ID del usuario.
            map_id: ID del mapa (opcional, si no se provee busca en todos los mapas).

        Returns:
            MessageSender del jugador o None si no existe.
        """
        return self._player_index.get_message_sender(user_id, map_id)

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
        return self._player_index.get_all_message_senders_in_map(map_id, exclude_user_id)

    def get_player_count_in_map(self, map_id: int) -> int:
        """Obtiene el número de jugadores en un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Número de jugadores en el mapa.
        """
        return self._player_index.get_player_count_in_map(map_id)

    def remove_player_from_all_maps(self, user_id: int) -> None:
        """Remueve un jugador de todos los mapas.

        Args:
            user_id: ID del usuario.
        """
        self._player_index.remove_player_from_all_maps(user_id)

    def get_all_connected_players(self) -> list[str]:
        """Obtiene la lista de nombres de todos los jugadores conectados.

        Returns:
            Lista de nombres de usuario conectados.
        """
        return self._player_index.get_all_connected_players()

    def get_all_connected_user_ids(self) -> list[int]:
        """Obtiene la lista de user_ids de todos los jugadores conectados.

        Returns:
            Lista de user_ids conectados.
        """
        return self._player_index.get_all_connected_user_ids()

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
        self._ground_index.add_ground_item(map_id, x, y, item)

    def get_ground_items(self, map_id: int, x: int, y: int) -> list[dict[str, int | str | None]]:
        """Obtiene todos los items en un tile específico.

        Args:
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.

        Returns:
            Lista de items en ese tile (vacía si no hay items).
        """
        return self._ground_index.get_ground_items(map_id, x, y)

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
        return self._ground_index.remove_ground_item(map_id, x, y, item_index)

    def clear_ground_items(self, map_id: int) -> int:
        """Limpia todos los items de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Cantidad de items removidos.
        """
        return self._ground_index.clear_ground_items(map_id)

    def get_ground_items_count(self, map_id: int) -> int:
        """Obtiene la cantidad total de items en el suelo de un mapa.

        Args:
            map_id: ID del mapa.

        Returns:
            Cantidad de items.
        """
        return self._ground_index.get_ground_items_count(map_id)

    @property
    def ground_items_repo(self) -> "GroundItemsRepository | None":  # noqa: UP037
        """Repositorio de ground items (getter/setter para propagar al índice)."""
        return self._ground_items_repo

    @ground_items_repo.setter
    def ground_items_repo(self, repo: "GroundItemsRepository | None") -> None:  # noqa: UP037
        self._ground_items_repo = repo
        self._ground_index.ground_items_repo = repo

    async def _persist_ground_items(self, map_id: int) -> None:
        """Persiste los ground items de un mapa en Redis.

        Args:
            map_id: ID del mapa.
        """
        await self._ground_index.persist_ground_items(map_id)

    async def load_ground_items(self, map_id: int) -> None:
        """Carga los ground items de un mapa desde Redis.

        Args:
            map_id: ID del mapa.
        """
        await self._ground_index.load_ground_items(map_id)

    def load_map_data(self, map_id: int, map_file_path: str | Path) -> None:
        """Carga metadatos y tiles bloqueados de un mapa delegando en el loader."""
        result = self._metadata_loader.load_map_data(map_id, map_file_path)
        self._map_sizes[map_id] = (result.width, result.height)
        self._blocked_tiles[map_id] = result.blocked_tiles
        self._exit_index.update(result.exit_tiles)

        logger.info(
            "Mapa %d cargado: %dx%d, %d tiles bloqueados, %d exits",
            map_id,
            result.width,
            result.height,
            len(result.blocked_tiles),
            result.exit_count,
        )

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
        return self._exit_index.get_exit_tile(map_id, x, y)

    def block_tile(self, map_id: int, x: int, y: int) -> None:
        """Marca una puerta como cerrada (bloquea movimiento pero no es un tile "bloqueado").

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
        """
        self._door_state.block(map_id, x, y)

    def unblock_tile(self, map_id: int, x: int, y: int) -> None:
        """Marca una puerta como abierta (permite movimiento).

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
        """
        self._door_state.unblock(map_id, x, y)

    def is_door_closed(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si hay una puerta cerrada en una posición.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si hay una puerta cerrada, False en caso contrario.
        """
        return self._door_state.is_closed(map_id, x, y)
