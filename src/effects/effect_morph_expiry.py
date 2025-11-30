"""Efecto periódico para restaurar apariencia morfeada expirada."""

import logging
import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class MorphExpiryEffect(TickEffect):
    """Efecto que verifica y restaura apariencias morfeadas expiradas."""

    _last_check_time: float = 0.0  # Timestamp de última verificación (clase)

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        account_repo: AccountRepository | None = None,
        interval_seconds: float = 5.0,
    ) -> None:
        """Inicializa el efecto de expiración de mimetismo.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas.
            account_repo: Repositorio de cuentas (opcional, necesario para apariencia original).
            interval_seconds: Intervalo en segundos entre verificaciones (default: 5s).
        """
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.account_repo = account_repo
        self.interval_seconds = interval_seconds

    async def apply(
        self,
        _user_id: int,
        _player_repo: PlayerRepository,
        _message_sender: MessageSender | None,
    ) -> None:
        """Verifica y restaura apariencias morfeadas expiradas.

        Nota: Este efecto se ejecuta una vez por jugador, pero solo procesa
        si han pasado suficientes segundos desde la última verificación global.

        Args:
            _user_id: ID del usuario (no usado, requerido por TickEffect).
            _player_repo: Repositorio de jugadores (no usado, requerido por TickEffect).
            _message_sender: Enviador de mensajes (no usado, requerido por TickEffect).
        """
        current_time = time.time()

        # Solo ejecutar si han pasado suficientes segundos desde la última verificación
        if current_time - MorphExpiryEffect._last_check_time < self.interval_seconds:
            return

        # Actualizar timestamp de última verificación
        MorphExpiryEffect._last_check_time = current_time

        # Obtener todos los user_ids conectados
        connected_user_ids = self.map_manager.get_all_connected_user_ids()

        # Verificar cada jugador conectado
        for user_id in connected_user_ids:
            # Obtener apariencia morfeada
            morphed = await self.player_repo.get_morphed_appearance(user_id)
            if not morphed:
                continue

            morphed_until = morphed.get("morphed_until", 0.0)

            # Si expiró, restaurar apariencia original
            if current_time >= morphed_until:
                # Limpiar apariencia morfeada
                await self.player_repo.clear_morphed_appearance(user_id)

                # Obtener apariencia original desde account
                original_body = 1
                original_head = 1
                if self.account_repo:
                    account_data = await self.account_repo.get_account_by_user_id(user_id)
                    if account_data:
                        original_body = int(account_data.get("char_race", 1))
                        original_head = int(account_data.get("char_head", 1))
                        if original_body == 0:
                            original_body = 1

                # Obtener posición y heading
                position = await self.player_repo.get_position(user_id)
                if position:
                    map_id = position["map"]
                    heading = position.get("heading", 3)

                    # Enviar CHARACTER_CHANGE al jugador
                    message_sender = self.map_manager.get_message_sender(user_id)
                    if message_sender:
                        await message_sender.send_character_change(
                            char_index=user_id,
                            body=original_body,
                            head=original_head,
                            heading=heading,
                        )

                        # Broadcast a otros jugadores en el mapa
                        other_senders = self.map_manager.get_all_message_senders_in_map(
                            map_id, exclude_user_id=user_id
                        )
                        for sender in other_senders:
                            await sender.send_character_change(
                                char_index=user_id,
                                body=original_body,
                                head=original_head,
                                heading=heading,
                            )

                        logger.info(
                            "Apariencia morfeada restaurada para user_id %d (body=%d head=%d)",
                            user_id,
                            original_body,
                            original_head,
                        )

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo en segundos entre aplicaciones del efecto.

        Returns:
            Intervalo en segundos.
        """
        return self.interval_seconds

    def get_name(self) -> str:  # noqa: PLR6301
        """Retorna el nombre del efecto.

        Returns:
            Nombre del efecto.
        """
        return "MorphExpiry"
