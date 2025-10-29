"""Servicio para spawnear NPCs en el MapManager."""

import logging
from typing import TYPE_CHECKING, Any

from src.models.npc import NPC
from src.services.game.npc_service import NPCService

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender

logger = logging.getLogger(__name__)


class NPCMapSpawner:
    """Maneja el spawning de NPCs en el MapManager y envío al cliente."""

    def __init__(self, map_manager: MapManager) -> None:
        """Inicializa el spawner.

        Args:
            map_manager: Gestor de mapas donde se agregarán los NPCs.
        """
        self.map_manager = map_manager

    async def spawn_npcs_for_player(
        self,
        npc_list: list[dict[str, Any]],
        message_sender: MessageSender,
    ) -> None:
        """Spawnea NPCs en el MapManager y los envía al cliente.

        Args:
            npc_list: Lista de NPCs a spawnear (del NPCWorldManager).
            message_sender: MessageSender para enviar al cliente.
        """
        npc_service = NPCService.get_instance()

        for npc_data in npc_list:
            # Obtener datos completos del NPC
            full_npc_data = npc_service.get_npc_by_id(npc_data["id"])

            if not full_npc_data:
                logger.warning("No se encontró NPC con ID %d", npc_data["id"])
                continue

            # Crear objeto NPC para MapManager
            npc_obj = NPC(
                npc_id=npc_data["id"],
                char_index=10001 + hash(npc_data["instance_id"]) % 50000,  # CharIndex único
                instance_id=str(npc_data["instance_id"]),
                name=npc_data["name"],
                description=full_npc_data.get("descripcion", full_npc_data.get("description", "")),
                body_id=full_npc_data.get("body_id", 1),
                head_id=full_npc_data.get("head_id", 0),
                x=npc_data["x"],
                y=npc_data["y"],
                map_id=npc_data["map"],
                heading=npc_data["direction"],
                hp=full_npc_data.get("hp_max", 100),
                max_hp=full_npc_data.get("hp_max", 100),
                level=full_npc_data.get("nivel", full_npc_data.get("level", 1)),
                is_hostile=npc_data["hostile"],
                is_attackable=full_npc_data.get(
                    "es_atacable", full_npc_data.get("is_attackable", True)
                ),
                is_merchant=npc_data["trader"],
            )

            # Agregar al MapManager
            self.map_manager.add_npc(npc_obj.map_id, npc_obj)

            # Enviar CHARACTER_CREATE al cliente
            await message_sender.send_character_create(
                char_index=npc_obj.char_index,
                body=npc_obj.body_id,
                head=npc_obj.head_id,
                heading=npc_obj.heading,
                x=npc_obj.x,
                y=npc_obj.y,
                name=npc_obj.name,
            )

        logger.info("Spawneados %d NPCs para el jugador", len(npc_list))
