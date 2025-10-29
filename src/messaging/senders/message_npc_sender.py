"""Componente para enviar NPCs al cliente usando protocolo de personajes."""

import hashlib
import logging
from collections.abc import Mapping, MutableMapping
from typing import TYPE_CHECKING, Any, cast

from src.network.msg_character import (
    build_character_change_response,
    build_character_create_response,
    build_character_move_response,
    build_character_remove_response,
)

if TYPE_CHECKING:
    from src.network.client_connection import ClientConnection

logger = logging.getLogger(__name__)


class NPCMessageSender:
    """Maneja el envío de NPCs al cliente usando paquetes de personaje."""

    def __init__(self, connection: ClientConnection) -> None:
        """Inicializa el sender de NPCs.

        Args:
            connection: Conexión con el cliente.
        """
        self.connection = connection
        # Contador para índices únicos de NPCs
        self._next_npc_index = 1000  # Empezar desde 1000 para no conflictuar con jugadores

    @staticmethod
    def get_npc_index(instance_id: str) -> int:
        """Convierte instance_id de NPC a char_index único para cliente.

        Args:
            instance_id: ID único del NPC (map_npcid_x_y)

        Returns:
            Índice único para cliente (1000-9999)
        """
        # Hash del instance_id para generar índice consistente
        hash_obj = hashlib.sha256(instance_id.encode())
        hash_int = int(hash_obj.hexdigest()[:8], 16)

        # Mapear a rango 1000-9999 para no conflictuar con jugadores
        return 1000 + (hash_int % 9000)  # Entre 1000-9999

    async def send_npc_create(self, npc_data: Mapping[str, Any]) -> None:
        """Envía NPC al cliente usando CHARACTER_CREATE.

        Args:
            npc_data: Datos del NPC con campos: id, name, x, y, direction, hostile, appearance.
        """
        instance_id = str(npc_data["instance_id"])
        char_index = NPCMessageSender.get_npc_index(instance_id)

        # Extraer apariencia del NPC
        appearance: Mapping[str, Any] = cast("Mapping[str, Any]", npc_data.get("appearance") or {})
        body_value = appearance.get("body", npc_data["id"])
        head_value = appearance.get("head", 1)
        body = int(body_value)
        head = int(head_value)

        # Color del nick según hostilidad
        hostile = bool(npc_data.get("hostile", False))
        nick_color = 2 if hostile else 0  # 2=Hostil, 0=Normal (rango byte)

        # Privilegios (para mostrar status especial)
        is_trader = bool(npc_data.get("trader", False))
        privileges = 2 if is_trader else 0  # 2 = Trader, 0 = Normal

        name = str(npc_data["name"])

        await self.connection.send(
            build_character_create_response(
                char_index=char_index,
                body=body,
                head=head,
                heading=int(npc_data.get("direction", 3)),
                x=int(npc_data["x"]),
                y=int(npc_data["y"]),
                weapon=0,  # NPCs sin arma por defecto
                shield=0,
                helmet=0,
                fx=0,  # Sin efectos especiales
                loops=0,
                name=name,
                nick_color=nick_color,
                privileges=privileges,
            )
        )

        logger.debug(
            "[%s] NPC CREATE: %s (index=%d) at (%d,%d) hostile=%s",
            self.connection.address,
            name,
            char_index,
            int(npc_data["x"]),
            int(npc_data["y"]),
            hostile,
        )

    async def send_npc_remove(self, instance_id: str) -> None:
        """Envía remoción de NPC al cliente.

        Args:
            instance_id: ID único del NPC a remover.
        """
        char_index = NPCMessageSender.get_npc_index(instance_id)

        await self.connection.send(build_character_remove_response(char_index))

        logger.debug(
            "[%s] NPC REMOVE: index=%d (instance=%s)",
            self.connection.address,
            char_index,
            instance_id,
        )

    async def send_npc_move(self, npc_data: Mapping[str, Any]) -> None:
        """Envía movimiento de NPC al cliente.

        Args:
            npc_data: Datos del NPC con posición actualizada.
        """
        instance_id = str(npc_data["instance_id"])
        char_index = NPCMessageSender.get_npc_index(instance_id)

        await self.connection.send(
            build_character_move_response(
                char_index=char_index,
                x=int(npc_data["x"]),
                y=int(npc_data["y"]),
            )
        )

        logger.debug(
            "[%s] NPC MOVE: index=%d to (%d,%d)",
            self.connection.address,
            char_index,
            int(npc_data["x"]),
            int(npc_data["y"]),
        )

    async def send_npc_change(self, npc_data: Mapping[str, Any]) -> None:
        """Envía cambio de apariencia/dirección de NPC.

        Args:
            npc_data: Datos del NPC con cambios de apariencia.
        """
        instance_id = str(npc_data["instance_id"])
        char_index = NPCMessageSender.get_npc_index(instance_id)

        # Extraer apariencia
        appearance: Mapping[str, Any] = cast("Mapping[str, Any]", npc_data.get("appearance") or {})
        body_value = appearance.get("body", npc_data["id"])
        head_value = appearance.get("head", 1)
        body = int(body_value)
        head = int(head_value)

        await self.connection.send(
            build_character_change_response(
                char_index=char_index,
                body=body,
                head=head,
                heading=int(npc_data.get("direction", 3)),
                weapon=0,
                shield=0,
                helmet=0,
                fx=int(npc_data.get("combat_fx", 0)),  # Efecto de combate
                loops=1,
            )
        )

        logger.debug(
            "[%s] NPC CHANGE: index=%d direction=%d",
            self.connection.address,
            char_index,
            int(npc_data.get("direction", 3)),
        )

    async def send_npc_combat_start(self, npc_data: MutableMapping[str, Any]) -> None:
        """Envía efecto visual de inicio de combate.

        Args:
            npc_data: NPC que entra en combate.
        """
        # Añadir efecto visual de combate
        npc_data["combat_fx"] = 1  # ID de efecto de combate

        await self.send_npc_change(npc_data)

        name = str(npc_data["name"])

        logger.info(
            "[%s] NPC COMBAT START: %s (index=%d)",
            self.connection.address,
            name,
            NPCMessageSender.get_npc_index(str(npc_data["instance_id"])),
        )

    async def send_npc_combat_end(self, npc_data: MutableMapping[str, Any]) -> None:
        """Envía efecto visual de fin de combate.

        Args:
            npc_data: NPC que sale de combate.
        """
        # Remover efecto de combate
        npc_data["combat_fx"] = 0

        await self.send_npc_change(npc_data)

        name = str(npc_data["name"])

        logger.info(
            "[%s] NPC COMBAT END: %s (index=%d)",
            self.connection.address,
            name,
            NPCMessageSender.get_npc_index(str(npc_data["instance_id"])),
        )

    async def sync_all_npcs(self, spawned_npcs: Mapping[str, Mapping[str, Any]]) -> None:
        """Sincroniza todos los NPCs spawneados con el cliente.

        Args:
            spawned_npcs: Diccionario de NPCs spawneados.
        """
        for npc_data in spawned_npcs.values():
            await self.send_npc_create(npc_data)

        logger.info(
            "[%s] NPC SYNC: Enviados %d NPCs al cliente",
            self.connection.address,
            len(spawned_npcs),
        )
