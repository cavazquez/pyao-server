"""Órdenes de mascotas validadas por propietario y por identidad de instancia."""

import time
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from src.services.npc.npc_service import NPCService


class PetOrders:
    """No acepta char_index como identidad ni autoridad de propiedad del cliente."""

    def __init__(self, npc_service: NPCService) -> None:
        """Conserva el mundo actual y el repositorio persistente."""
        self.npc_service = npc_service

    def snapshot(self, user: int) -> dict[str, Any]:
        """Deriva exclusivamente las mascotas activas del dueño autenticado.

        Returns:
            Identidad, vida, orden y expiración; no altera NPCs.
        """
        now = time.time()
        pets = [
            pet
            for pet in self.npc_service.map_manager.get_player_pets(user)
            if pet.summoned_by_user_id == user
            and pet.hp > 0
            and (pet.is_tamed or pet.summoned_until > now)
        ]
        return {
            "pets": [
                {
                    "id": pet.instance_id,
                    "index": pet.char_index,
                    "name": pet.name,
                    "hp": pet.hp,
                    "max_hp": pet.max_hp,
                    "map": pet.map_id,
                    "order": pet.pet_order,
                    "expires": int(pet.summoned_until),
                    "permanent": pet.is_tamed,
                }
                for pet in pets
            ]
        }

    async def command(self, user: int, instance: str, order: str, identity: str) -> dict[str, Any]:
        """Confirma seguir/esperar bajo WATCH sin alterar combate, curación ni daños.

        Returns:
            Resultado de la orden del propietario vigente.

        Raises:
            ValueError: Si la orden o identidad son inválidas.
        """
        UUID(instance)
        if order not in {"follow", "wait", "release"}:
            message = "Orden de mascota inválida"
            raise ValueError(message)
        key = RedisKeys.npc_instance(instance)
        now = time.time()

        def decide(snapshot: Snapshot) -> Decision:
            pet = cast("dict[str, str]", snapshot[key])
            if (
                int(pet.get("summoned_by_user_id", 0)) != user
                or int(pet.get("hp", 0)) <= 0
                or not (
                    pet.get("is_tamed", "False").lower() == "true"
                    or float(pet.get("summoned_until", 0)) > now
                )
            ):
                return Decision(
                    {
                        "applied": False,
                        "message": "La mascota ya no te pertenece o no está activa.",
                    },
                    {},
                )
            return Decision(
                {
                    "applied": True,
                    "message": "La mascota te seguirá."
                    if order == "follow"
                    else "La mascota esperará."
                    if order == "wait"
                    else "Mascota liberada.",
                },
                {
                    key: {"hp": "0", "summoned_until": "0", "is_tamed": "False"}
                    if order == "release"
                    else {"pet_order": order}
                },
            )

        result = await transact(
            self.npc_service.npc_repository.redis.redis,
            (Resource(key, "hash"),),
            identity,
            {"pet": instance, "owner": user, "order": order},
            decide,
        )
        if result["applied"]:
            pet = self.npc_service.map_manager.get_npc_by_instance(instance)
            if pet is not None and pet.summoned_by_user_id == user:
                if order == "release":
                    pet.hp = 0
                    await self.npc_service.remove_npc(pet)
                else:
                    pet.pet_order = order
        return result
