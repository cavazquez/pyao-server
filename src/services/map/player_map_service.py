"""Servicio para manejar spawn y transiciones de jugadores entre mapas."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


@dataclass
class PlayerVisualData:
    """Datos visuales de un jugador para CHARACTER_CREATE."""

    user_id: int
    username: str
    char_body: int
    char_head: int


class PlayerMapService:
    """Servicio que encapsula la lógica de spawn y transición de jugadores entre mapas.

    Este servicio centraliza toda la lógica duplicada relacionada con:
    - Aparecer en un mapa (login inicial)
    - Cambiar de mapa (transiciones)
    - Enviar entidades del mapa (jugadores, NPCs, ground items)
    """

    def __init__(
        self,
        player_repo: PlayerRepository,
        account_repo: AccountRepository,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService,
    ) -> None:
        """Inicializa el servicio de mapas de jugador.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast multijugador.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service

    async def _get_player_visual_data(self, user_id: int) -> PlayerVisualData:
        """Obtiene los datos visuales de un jugador (body, head, username).

        Args:
            user_id: ID del jugador.

        Returns:
            PlayerVisualData con los datos del jugador.
        """
        # Valores por defecto
        char_body = 1
        char_head = 1
        username = f"Player{user_id}"

        # Obtener datos de la cuenta
        account_data = await self.account_repo.get_account_by_user_id(user_id)
        if account_data:
            char_body = int(account_data.get("char_race", 1))
            char_head = int(account_data.get("char_head", 1))
            username = account_data.get("username", f"Player{user_id}")

            # Validar body (no puede ser 0)
            if char_body == 0:
                char_body = 1

        return PlayerVisualData(
            user_id=user_id,
            username=username,
            char_body=char_body,
            char_head=char_head,
        )

    async def _send_players_in_map(
        self,
        map_id: int,
        message_sender: MessageSender,
        exclude_user_id: int | None = None,
    ) -> int:
        """Envía CHARACTER_CREATE de todos los jugadores en un mapa.

        Args:
            map_id: ID del mapa.
            message_sender: MessageSender del jugador receptor.
            exclude_user_id: ID del jugador a excluir (opcional).

        Returns:
            Número de jugadores enviados.
        """
        existing_players = self.map_manager.get_players_in_map(map_id)
        players_sent = 0

        for other_user_id in existing_players:
            # Excluir al jugador especificado
            if exclude_user_id and other_user_id == exclude_user_id:
                continue

            # Obtener posición del otro jugador
            other_position = await self.player_repo.get_position(other_user_id)
            if not other_position:
                continue

            # Obtener datos visuales del otro jugador
            other_visual = await self._get_player_visual_data(other_user_id)

            # Enviar CHARACTER_CREATE
            await message_sender.send_character_create(
                char_index=other_user_id,
                body=other_visual.char_body,
                head=other_visual.char_head,
                heading=other_position.get("heading", 3),
                x=other_position["x"],
                y=other_position["y"],
                name=other_visual.username,
            )
            await asyncio.sleep(0.01)
            players_sent += 1

        logger.debug("Enviados %d jugadores del mapa %d", players_sent, map_id)
        return players_sent

    async def _send_npcs_in_map(self, map_id: int, message_sender: MessageSender) -> int:
        """Envía CHARACTER_CREATE de todos los NPCs en un mapa.

        Args:
            map_id: ID del mapa.
            message_sender: MessageSender del jugador receptor.

        Returns:
            Número de NPCs enviados.
        """
        npcs = self.map_manager.get_npcs_in_map(map_id)
        npcs_sent = 0

        for npc in npcs:
            await message_sender.send_character_create(
                char_index=npc.char_index,
                body=npc.body_id,
                head=npc.head_id,
                heading=npc.heading,
                x=npc.x,
                y=npc.y,
                weapon=0,
                shield=0,
                helmet=0,
                fx=0,
                loops=0,
                name=npc.name,
            )
            await asyncio.sleep(0.01)
            npcs_sent += 1

        logger.debug("Enviados %d NPCs del mapa %d", npcs_sent, map_id)
        return npcs_sent

    async def _send_ground_items_in_map(self, map_id: int, message_sender: MessageSender) -> int:
        """Envía OBJECT_CREATE de todos los ground items en un mapa.

        Args:
            map_id: ID del mapa.
            message_sender: MessageSender del jugador receptor.

        Returns:
            Número de items enviados.
        """
        items_sent = 0

        # Acceder a ground items del MapManager
        for (item_map_id, x, y), items in self.map_manager._ground_items.items():  # noqa: SLF001
            if item_map_id != map_id:
                continue

            for item in items:
                grh_index = item.get("grh_index")
                if grh_index and isinstance(grh_index, int):
                    await message_sender.send_object_create(x, y, grh_index)
                    items_sent += 1
                    await asyncio.sleep(0.01)

        if items_sent > 0:
            logger.debug("Enviados %d ground items del mapa %d", items_sent, map_id)

        return items_sent

    async def spawn_in_map(
        self,
        user_id: int,
        map_id: int,
        x: int,
        y: int,
        heading: int,
        message_sender: MessageSender,
    ) -> None:
        """Spawnea un jugador en un mapa (usado en login inicial).

        Este método NO envía CHANGE_MAP ni remueve del mapa anterior,
        ya que el jugador está apareciendo por primera vez.

        Args:
            user_id: ID del jugador.
            map_id: ID del mapa.
            x: Posición X.
            y: Posición Y.
            heading: Dirección del jugador.
            message_sender: MessageSender del jugador.
        """
        # Obtener datos visuales del jugador
        visual_data = await self._get_player_visual_data(user_id)

        # 1. Agregar jugador al mapa en MapManager
        self.map_manager.add_player(map_id, user_id, message_sender, visual_data.username)

        # 2. Enviar CHARACTER_CREATE del propio jugador
        await message_sender.send_character_create(
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            heading=heading,
            x=x,
            y=y,
            name=visual_data.username,
        )

        # 3. Enviar todos los jugadores existentes en el mapa
        await self._send_players_in_map(map_id, message_sender, exclude_user_id=user_id)

        # 4. Enviar todos los NPCs del mapa
        await self._send_npcs_in_map(map_id, message_sender)

        # 5. Enviar todos los ground items del mapa
        await self._send_ground_items_in_map(map_id, message_sender)

        # 6. Broadcast CHARACTER_CREATE a otros jugadores
        await self.broadcast_service.broadcast_character_create(
            map_id=map_id,
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            heading=heading,
            x=x,
            y=y,
            name=visual_data.username,
        )

        logger.info(
            "Jugador %s (ID:%d) spawneado en mapa %d pos (%d,%d)",
            visual_data.username,
            user_id,
            map_id,
            x,
            y,
        )

    async def transition_to_map(
        self,
        user_id: int,
        current_map: int,
        current_x: int,
        current_y: int,
        new_map: int,
        new_x: int,
        new_y: int,
        heading: int,
        message_sender: MessageSender,
    ) -> None:
        """Transiciona un jugador de un mapa a otro (usado en cambios de mapa).

        Este método ejecuta la secuencia completa de 12 pasos para cambiar de mapa.

        Args:
            user_id: ID del jugador.
            current_map: ID del mapa actual.
            current_x: Posición X actual.
            current_y: Posición Y actual.
            new_map: ID del nuevo mapa.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            heading: Dirección del jugador.
            message_sender: MessageSender del jugador.
        """
        # Obtener datos visuales del jugador
        visual_data = await self._get_player_visual_data(user_id)

        # 1. Enviar CHANGE_MAP (cliente carga nuevo mapa)
        await message_sender.send_change_map(new_map)

        # 2. Delay para que el cliente cargue el mapa (crítico)
        await asyncio.sleep(0.1)

        # 3. Actualizar posición en Redis ANTES de POS_UPDATE
        await self.player_repo.set_position(user_id, new_x, new_y, new_map, heading)

        # 4. Enviar POS_UPDATE (cliente posiciona jugador)
        await message_sender.send_pos_update(new_x, new_y)

        # 5. Remover jugador del mapa anterior en MapManager
        self.map_manager.remove_player(current_map, user_id)

        # 6. Broadcast CHARACTER_REMOVE en mapa anterior
        await self.broadcast_service.broadcast_character_remove(current_map, user_id)

        # 7. Agregar jugador al nuevo mapa en MapManager
        self.map_manager.add_player(new_map, user_id, message_sender, visual_data.username)

        # 8. Enviar CHARACTER_CREATE del propio jugador
        await message_sender.send_character_create(
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            heading=heading,
            x=new_x,
            y=new_y,
            name=visual_data.username,
        )

        # 9. Enviar todos los jugadores existentes en el nuevo mapa
        await self._send_players_in_map(new_map, message_sender, exclude_user_id=user_id)

        # 10. Enviar todos los NPCs del nuevo mapa
        await self._send_npcs_in_map(new_map, message_sender)

        # 11. Enviar todos los objetos del suelo en el nuevo mapa
        await self._send_ground_items_in_map(new_map, message_sender)

        # 12. Broadcast CHARACTER_CREATE del jugador a otros en el nuevo mapa
        await self.broadcast_service.broadcast_character_create(
            map_id=new_map,
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            heading=heading,
            x=new_x,
            y=new_y,
            name=visual_data.username,
        )

        logger.info(
            "Jugador %s (ID:%d) cambió de mapa: %d -> %d, pos (%d,%d) -> (%d,%d)",
            visual_data.username,
            user_id,
            current_map,
            new_map,
            current_x,
            current_y,
            new_x,
            new_y,
        )
