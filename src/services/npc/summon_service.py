"""Servicio para gestionar mascotas invocadas por jugadores."""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)

# Límite máximo de mascotas por jugador (como en VB6: MAXMASCOTAS = 3)
MAX_MASCOTAS = 3


class SummonService:
    """Servicio para gestionar mascotas invocadas por jugadores."""

    def __init__(
        self,
        npc_repository: NPCRepository,
        player_repository: PlayerRepository,
    ) -> None:
        """Inicializa el servicio de invocación.

        Args:
            npc_repository: Repositorio de NPCs.
            player_repository: Repositorio de jugadores.
        """
        self.npc_repository = npc_repository
        self.player_repository = player_repository

    async def get_player_pets_count(self, user_id: int) -> int:
        """Obtiene el número de mascotas activas de un jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Número de mascotas activas.
        """
        # Obtener todas las mascotas del jugador desde Redis
        # Usamos un patrón para buscar NPCs con summoned_by_user_id = user_id
        # Por ahora, iteramos todos los NPCs (puede optimizarse con un índice)
        all_npcs = await self.npc_repository.get_all_npcs()
        return sum(
            1 for npc in all_npcs if npc.summoned_by_user_id == user_id and npc.summoned_until > 0
        )

    async def can_summon(self, user_id: int, count: int = 1) -> tuple[bool, str]:
        """Verifica si un jugador puede invocar más mascotas.

        Args:
            user_id: ID del jugador.
            count: Número de mascotas a invocar.

        Returns:
            Tupla (puede_invocar, mensaje_error).
        """
        current_pets = await self.get_player_pets_count(user_id)
        if current_pets >= MAX_MASCOTAS:
            return (False, f"No puedes invocar más mascotas. Límite: {MAX_MASCOTAS}")

        if current_pets + count > MAX_MASCOTAS:
            available_slots = MAX_MASCOTAS - current_pets
            return (
                False,
                f"No puedes invocar {count} mascotas. Solo puedes invocar {available_slots} más.",
            )

        return (True, "")

    async def get_player_pets(self, user_id: int) -> list[str]:
        """Obtiene la lista de instance_ids de las mascotas de un jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Lista de instance_ids de las mascotas activas.
        """
        all_npcs = await self.npc_repository.get_all_npcs()
        return [
            npc.instance_id
            for npc in all_npcs
            if npc.summoned_by_user_id == user_id and npc.summoned_until > 0
        ]

    async def register_pet(self, user_id: int, npc_instance_id: str) -> bool:
        """Registra una mascota para un jugador.

        Nota: La mascota ya debe tener los campos summoned_by_user_id y summoned_until
        configurados en el NPC. Este método solo verifica el límite.

        Args:
            user_id: ID del jugador.
            npc_instance_id: ID de la instancia del NPC invocado.

        Returns:
            True si se registró correctamente, False si se excedió el límite.
        """
        # Verificar límite antes de registrar
        can_summon, error_msg = await self.can_summon(user_id, 1)
        if not can_summon:
            logger.warning("No se puede registrar mascota para user_id %d: %s", user_id, error_msg)
            return False

        logger.debug("Mascota registrada para user_id %d: instance_id=%s", user_id, npc_instance_id)
        return True
