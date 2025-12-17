"""Handler especializado para spawn y posicionamiento del jugador durante login."""

import logging
from typing import TYPE_CHECKING

from src.services.player.player_service import PlayerService

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.player_map_service import PlayerMapService

logger = logging.getLogger(__name__)

# Constantes para tamaño del mapa
MAX_MAP_COORDINATE = 100


class LoginSpawnHandler:
    """Handler especializado para spawn y posicionamiento del jugador durante login."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        map_manager: MapManager | None,
        player_map_service: PlayerMapService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler de spawn.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas.
            player_map_service: Servicio de mapas de jugador.
            message_sender: Enviador de mensajes.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.player_map_service = player_map_service
        self.message_sender = message_sender

    def find_free_spawn_position(self, position: dict[str, int]) -> dict[str, int]:
        """Busca una posición libre cercana si la posición de spawn está ocupada.

        Args:
            position: Posición original de spawn.

        Returns:
            Posición libre (original o una cercana).
        """
        if not self.map_manager:
            return position

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # Verificar si la posición original está libre
        if not self.map_manager.is_tile_occupied(map_id, x, y):
            return position

        # Posición ocupada, buscar una libre cercana
        logger.info(
            "🧭 Spawn (%d,%d) en mapa %d ocupado, buscando casilla libre...",
            x,
            y,
            map_id,
        )

        # Buscar en espiral hacia afuera (radio 1-5 tiles)
        for radius in range(1, 6):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    # Solo verificar el borde del radio actual
                    if abs(dx) != radius and abs(dy) != radius:
                        continue

                    new_x = x + dx
                    new_y = y + dy

                    # Verificar que esté dentro del mapa
                    if (
                        new_x < 1
                        or new_y < 1
                        or new_x > MAX_MAP_COORDINATE
                        or new_y > MAX_MAP_COORDINATE
                    ):
                        continue

                    # Verificar que no esté bloqueado y no esté ocupado
                    if self.map_manager.can_move_to(
                        map_id, new_x, new_y
                    ) and not self.map_manager.is_tile_occupied(map_id, new_x, new_y):
                        logger.info(
                            "🟢 Casilla libre en (%d,%d), moviendo spawn de (%d,%d)",
                            new_x,
                            new_y,
                            x,
                            y,
                        )
                        return {
                            "x": new_x,
                            "y": new_y,
                            "map": map_id,
                            "heading": position.get("heading", 3),  # Default heading: South
                        }

        # No se encontró casilla libre (muy raro)
        logger.warning(
            "⚠️ Sin casilla libre cerca de (%d,%d) en mapa %d, usando original",
            x,
            y,
            map_id,
        )
        return position

    async def spawn_player(self, user_id: int, username: str, position: dict[str, int]) -> None:
        """Realiza el spawn del jugador en el mundo usando PlayerMapService.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            position: Posición del jugador.
        """
        # Reproducir sonido de login
        await self.message_sender.play_sound_login()

        # Usar PlayerMapService para spawn (maneja toda la secuencia de 12 pasos)
        if self.player_map_service:
            # Para login, el jugador viene de "ningún mapa" (map 0)
            await self.player_map_service.transition_to_map(
                user_id=user_id,
                current_map=0,  # No viene de ningún mapa
                current_x=0,  # Posición inválida (no importa)
                current_y=0,  # Posición inválida (no importa)
                new_map=position["map"],
                new_x=position["x"],
                new_y=position["y"],
                heading=position.get("heading", 3),
                message_sender=self.message_sender,
            )
        else:
            # Fallback por si acaso (no debería pasar con inyección correcta)
            logger.error("PlayerMapService no disponible para spawn, usando fallback")
            player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
            await player_service.spawn_character(user_id, username, position)
            await self.message_sender.send_pos_update(position["x"], position["y"])

        # Mostrar efecto visual de spawn
        await self.message_sender.play_effect_spawn(char_index=user_id)

    async def send_map_data(self, user_id: int, position: dict[str, int]) -> None:
        """Envía los datos del mapa al jugador.

        Args:
            user_id: ID del usuario.
            position: Posición del jugador.
        """
        # Cargar ground items desde Redis si no están en memoria
        if self.map_manager:
            await self.map_manager.load_ground_items(position["map"])

        # Usar PlayerMapService para spawnear en el mapa
        if self.player_map_service:
            await self.player_map_service.spawn_in_map(
                user_id=user_id,
                map_id=position["map"],
                x=position["x"],
                y=position["y"],
                heading=position.get("heading", 3),
                message_sender=self.message_sender,
            )
        else:
            logger.error("PlayerMapService no disponible para spawn en mapa")
