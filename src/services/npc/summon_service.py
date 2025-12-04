"""Servicio para gestionar mascotas invocadas por jugadores."""

import logging
from typing import TYPE_CHECKING

from src.constants.gameplay import MAX_PETS

if TYPE_CHECKING:
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


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
        if current_pets >= MAX_PETS:
            return (False, f"No puedes invocar más mascotas. Límite: {MAX_PETS}")

        if current_pets + count > MAX_PETS:
            available_slots = MAX_PETS - current_pets
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

    async def remove_pet(self, user_id: int, npc_instance_id: str) -> bool:
        """Remueve una mascota específica del registro del jugador.

        Nota: Esto NO elimina el NPC del mundo, solo lo desregistra.
        Para eliminar el NPC completamente, usar NPCService.remove_npc().

        Args:
            user_id: ID del jugador.
            npc_instance_id: ID de la instancia del NPC.

        Returns:
            True si se removió correctamente, False si no era mascota del jugador.
        """
        # Verificar que el NPC es mascota del jugador
        all_npcs = await self.npc_repository.get_all_npcs()
        pet_npc = next(
            (
                npc
                for npc in all_npcs
                if npc.instance_id == npc_instance_id and npc.summoned_by_user_id == user_id
            ),
            None,
        )

        if not pet_npc:
            logger.warning(
                "Intento de remover mascota que no pertenece al jugador: "
                "user_id=%d, instance_id=%s",
                user_id,
                npc_instance_id,
            )
            return False

        logger.debug(
            "Mascota removida del registro: user_id=%d, instance_id=%s", user_id, npc_instance_id
        )
        return True

    async def remove_all_player_pets(self, user_id: int) -> list[str]:
        """Remueve todas las mascotas de un jugador.

        Retorna la lista de instance_ids de las mascotas removidas.

        Args:
            user_id: ID del jugador.

        Returns:
            Lista de instance_ids de las mascotas que fueron removidas.
        """
        all_npcs = await self.npc_repository.get_all_npcs()
        player_pets = [
            npc for npc in all_npcs if npc.summoned_by_user_id == user_id and npc.summoned_until > 0
        ]

        pet_instance_ids = [pet.instance_id for pet in player_pets]
        logger.info(
            "Removiendo %d mascota(s) de user_id %d: %s",
            len(pet_instance_ids),
            user_id,
            pet_instance_ids,
        )

        return pet_instance_ids
