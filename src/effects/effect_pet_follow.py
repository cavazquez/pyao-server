"""Efecto periódico para que las mascotas sigan a su dueño."""

import logging
import time
from typing import TYPE_CHECKING

from src.constants.gameplay import MAX_PET_FOLLOW_DISTANCE
from src.effects.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.npc.npc_service import NPCService

logger = logging.getLogger(__name__)

# Alias for backwards compatibility
MAX_FOLLOW_DISTANCE = MAX_PET_FOLLOW_DISTANCE


class PetFollowEffect(TickEffect):
    """Efecto que hace que las mascotas sigan a su dueño."""

    _last_check_time: float = 0.0  # Timestamp de última verificación (clase)
    _execution_lock: bool = False  # Lock para evitar ejecuciones concurrentes (clase)

    def __init__(self, npc_service: NPCService, interval_seconds: float = 2.0) -> None:
        """Inicializa el efecto de seguimiento de mascotas.

        Args:
            npc_service: Servicio de NPCs para mover mascotas.
            interval_seconds: Intervalo en segundos entre verificaciones (default: 2s).
        """
        self.npc_service = npc_service
        self.interval_seconds = interval_seconds

    async def apply(
        self,
        _user_id: int,
        player_repo: PlayerRepository,
        _message_sender: MessageSender | None,
    ) -> None:
        """Hace que las mascotas sigan a su dueño si están muy lejos.

        Nota: Este efecto se ejecuta una vez por jugador, pero solo procesa
        si han pasado suficientes segundos desde la última verificación global.

        Args:
            _user_id: ID del usuario (no usado, requerido por TickEffect).
            player_repo: Repositorio de jugadores.
            _message_sender: Enviador de mensajes (no usado, requerido por TickEffect).
        """
        current_time = time.time()

        # Solo ejecutar si han pasado suficientes segundos desde la última verificación
        if current_time - PetFollowEffect._last_check_time < self.interval_seconds:
            return

        # Prevenir ejecuciones concurrentes (este efecto puede ser llamado desde múltiples threads)
        if PetFollowEffect._execution_lock:
            return

        # Bloquear ejecución y actualizar timestamp
        PetFollowEffect._execution_lock = True
        PetFollowEffect._last_check_time = current_time

        try:
            # Obtener todos los NPCs del mundo
            all_npcs = await self.npc_service.npc_repository.get_all_npcs()

            # Filtrar solo mascotas invocadas
            pets = [
                npc for npc in all_npcs if npc.summoned_by_user_id > 0 and npc.summoned_until > 0.0
            ]

            if not pets:
                return

            # Procesar cada mascota
            for pet in pets:
                owner_id = pet.summoned_by_user_id

                # Obtener posición del dueño
                owner_position = await player_repo.get_position(owner_id)
                if not owner_position:
                    # Dueño no conectado o no encontrado, saltar
                    continue

                # Verificar que están en el mismo mapa
                if owner_position["map"] != pet.map_id:
                    # Mascota está en otro mapa, saltar (no puede seguir entre mapas)
                    continue

                owner_x = owner_position["x"]
                owner_y = owner_position["y"]

                # Calcular distancia Manhattan
                distance = abs(pet.x - owner_x) + abs(pet.y - owner_y)

                # Si la mascota está muy lejos, hacerla seguir al dueño
                if distance > MAX_FOLLOW_DISTANCE:
                    logger.debug(
                        "Mascota %s (inst:%s) está a %d tiles de su dueño "
                        "(user_id %d), siguiendo...",
                        pet.name,
                        pet.instance_id,
                        distance,
                        owner_id,
                    )
                    await self._move_pet_towards_owner(pet, owner_x, owner_y)
        finally:
            # Desbloquear ejecución
            PetFollowEffect._execution_lock = False

    async def _move_pet_towards_owner(self, pet: NPC, owner_x: int, owner_y: int) -> None:
        """Mueve una mascota un paso hacia su dueño.

        Args:
            pet: Instancia de la mascota.
            owner_x: Coordenada X del dueño.
            owner_y: Coordenada Y del dueño.
        """
        # Verificar si la mascota está paralizada
        current_time = time.time()
        if pet.paralyzed_until > 0.0 and current_time < pet.paralyzed_until:
            logger.debug(
                "Mascota %s no puede seguir: está paralizada (queda %.1fs)",
                pet.name,
                pet.paralyzed_until - current_time,
            )
            return

        # Calcular dirección hacia el dueño
        dx = owner_x - pet.x
        dy = owner_y - pet.y

        # Decidir dirección prioritaria
        new_x = pet.x
        new_y = pet.y
        new_heading = pet.heading

        if abs(dx) > abs(dy):
            # Moverse horizontalmente primero
            if dx > 0:
                new_x += 1
                new_heading = 2  # Este
            else:
                new_x -= 1
                new_heading = 4  # Oeste
        # Moverse verticalmente
        elif dy > 0:
            new_y += 1
            new_heading = 3  # Sur
        else:
            new_y -= 1
            new_heading = 1  # Norte

        # Verificar que la nueva posición sea válida
        if not self.npc_service.map_manager.can_move_to(pet.map_id, new_x, new_y):
            return

        # Verificar que no esté ocupada
        if self.npc_service.map_manager.is_tile_occupied(pet.map_id, new_x, new_y):
            return

        # Guardar coordenadas anteriores para el log
        old_x = pet.x
        old_y = pet.y

        # Mover la mascota usando NPCService
        await self.npc_service.move_npc(pet, new_x, new_y, new_heading)

        logger.debug(
            "Mascota %s (inst:%s) se movió hacia dueño: (%d,%d) -> (%d,%d)",
            pet.name,
            pet.instance_id,
            old_x,
            old_y,
            new_x,
            new_y,
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
        return "PetFollow"
