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

    def reserve_spawn_position(
        self, position: dict[str, int], identity: str, *, sailing: bool = False
    ) -> dict[str, int] | None:
        """Reserva una llegada cercana sin ceder control ni pisar otro ocupante.

        Args:
            position: Posición guardada del personaje.
            identity: Token propio de este intento de login.
            sailing: Si el personaje debe permanecer sobre agua.

        Returns:
            Destino reservado o None si no hay espacio seguro en radio cinco.
        """
        if self.map_manager is None:
            return position
        map_id, x, y = position["map"], position["x"], position["y"]
        if not self.map_manager.has_map(map_id):
            return None
        resources = self.player_map_service.map_resources if self.player_map_service else None
        for radius in range(6):
            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    if max(abs(dx), abs(dy)) != radius:
                        continue
                    new_x, new_y = x + dx, y + dy
                    water = bool(resources and resources.has_water(map_id, new_x, new_y))
                    if water != sailing:
                        continue
                    if resources and (
                        (resources.is_blocked(map_id, new_x, new_y) and not water)
                        or resources.has_tree(map_id, new_x, new_y)
                        or resources.has_mine(map_id, new_x, new_y)
                    ):
                        continue
                    if self.map_manager.reserve_arrival(
                        identity, map_id, new_x, new_y, water=water
                    ):
                        return {**position, "x": new_x, "y": new_y}
        logger.warning("Sin llegada libre cerca de (%d,%d) en mapa %d", x, y, map_id)
        return None

    def release_spawn_position(self, identity: str, position: dict[str, int]) -> None:
        """Retira sólo la reserva propia, sin borrar un actor ya publicado."""
        if self.map_manager is not None:
            self.map_manager.release_positions(
                identity, (position["map"], position["x"], position["y"])
            )

    async def spawn_player(self, user_id: int, username: str, position: dict[str, int]) -> None:
        """Realiza el spawn del jugador en el mundo usando PlayerMapService.

        Args:
            user_id: ID del usuario.
            username: Nombre de usuario.
            position: Posición del jugador.
        """
        # El login entra desde ningún mapa: un único snapshot completo, incluyendo
        # suelo, NPCs aleatorios y desbloqueo de portales. Una transición seguida
        # de otro spawn enviaba las mismas entidades dos veces.
        if self.player_map_service:
            if self.map_manager:
                await self.map_manager.load_ground_items(position["map"])
            await self.message_sender.send_change_map(position["map"])
            await self.message_sender.send_pos_update(position["x"], position["y"])
            await self.player_map_service.spawn_in_map(
                user_id=user_id,
                map_id=position["map"],
                x=position["x"],
                y=position["y"],
                heading=position.get("heading", 3),
                message_sender=self.message_sender,
            )
        else:
            # Fallback por si acaso (no debería pasar con inyección correcta)
            logger.error("PlayerMapService no disponible para spawn, usando fallback")
            player_service = PlayerService(self.player_repo, self.message_sender, self.account_repo)
            await player_service.spawn_character(user_id, username, position)
            await self.message_sender.send_pos_update(position["x"], position["y"])

        # CHANGE_MAP detiene el audio anterior en el cliente. El sonido de login
        # debe empezar después de cargar el mapa y crear al actor.
        await self.message_sender.play_sound_login()
        await self.message_sender.play_effect_spawn(char_index=user_id)
        if self.map_manager:
            for observer in self.map_manager.get_all_message_senders_in_map(position["map"]):
                if observer is self.message_sender:
                    continue
                try:
                    await observer.play_effect_spawn(char_index=user_id)
                except OSError:
                    logger.warning("No se pudo enviar el FX de login al observador", exc_info=True)

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
