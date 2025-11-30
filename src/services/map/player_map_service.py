"""Servicio para manejar spawn y transiciones de jugadores entre mapas."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.account_repository import AccountRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.random_spawn_service import RandomSpawnService

from src.services.map.map_transition_steps import (
    MapTransitionContext,
    MapTransitionOrchestrator,
)

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
        random_spawn_service: RandomSpawnService | None = None,
    ) -> None:
        """Inicializa el servicio de mapas de jugador.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast multijugador.
            random_spawn_service: Servicio de spawns aleatorios (opcional).
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.random_spawn_service = random_spawn_service

        # Crear orquestador de transición con la secuencia predeterminada
        self.transition_orchestrator = MapTransitionOrchestrator.create_default_orchestrator(
            player_repo,
            map_manager,
            broadcast_service,
            self._send_players_in_map,
            self._send_npcs_in_map,
            self._send_ground_items_in_map,
        )

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

        # Verificar si el jugador tiene apariencia morfeada activa
        morphed = await self.player_repo.get_morphed_appearance(user_id)
        if morphed:
            morphed_until = morphed.get("morphed_until", 0.0)
            if time.time() < morphed_until:
                # Usar apariencia morfeada
                char_body = int(morphed.get("morphed_body", char_body))
                char_head = int(morphed.get("morphed_head", char_head))

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

    async def _unblock_exit_tiles(self, map_id: int, message_sender: MessageSender) -> int:
        """Envía BLOCK_POSITION(false) para tiles de exit que están bloqueados en el cliente.

        Este es un workaround para mapas donde los tiles de exit están marcados como
        bloqueados en el archivo .map del cliente, impidiendo que el jugador camine
        sobre ellos para activar el teleport.

        Args:
            map_id: ID del mapa.
            message_sender: MessageSender del jugador.

        Returns:
            Número de tiles desbloqueados.
        """
        unblocked = 0

        # Obtener todos los exit tiles del mapa desde MapManager
        exit_tiles = getattr(self.map_manager, "_exit_tiles", {})
        for exit_map_id, x, y in exit_tiles:
            if exit_map_id == map_id:
                # Enviar BLOCK_POSITION(false) para desbloquear el tile
                await message_sender.send_block_position(x, y, blocked=False)
                unblocked += 1
                await asyncio.sleep(0.001)  # Pequeño delay para no saturar

        if unblocked > 0:
            logger.debug("Desbloqueados %d tiles de exit en mapa %d", unblocked, map_id)

        return unblocked

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

        # 1b. Marcar ocupación de tile para el jugador en el índice espacial
        # Usamos old_x/old_y iguales a la posición inicial para centralizar la lógica
        self.map_manager.update_player_tile(user_id, map_id, x, y, x, y)

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

        # 4b. Spawneear NPCs aleatorios si hay áreas configuradas
        await self._spawn_random_npcs_for_player(map_id, x, y, message_sender)

        # 5. Enviar todos los ground items del mapa
        await self._send_ground_items_in_map(map_id, message_sender)

        # 6. Desbloquear tiles de exit (workaround para mapas con tiles bloqueados incorrectamente)
        await self._unblock_exit_tiles(map_id, message_sender)

        # 7. Broadcast CHARACTER_CREATE a otros jugadores
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

        Este método ahora usa el orquestador de transición para ejecutar la secuencia
        completa de 12 pasos de forma modular y mantenible.

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

        # Crear contexto de transición
        context = MapTransitionContext(
            user_id=user_id,
            username=visual_data.username,
            char_body=visual_data.char_body,
            char_head=visual_data.char_head,
            current_map=current_map,
            current_x=current_x,
            current_y=current_y,
            new_map=new_map,
            new_x=new_x,
            new_y=new_y,
            heading=heading,
            message_sender=message_sender,
        )

        # Ejecutar transición usando el orquestador
        await self.transition_orchestrator.execute_transition(context)

        # Spawneear NPCs aleatorios después de la transición (si hay áreas configuradas)
        await self._spawn_random_npcs_for_player(new_map, new_x, new_y, message_sender)

    async def teleport_in_same_map(
        self,
        user_id: int,
        map_id: int,
        old_x: int,
        old_y: int,
        new_x: int,
        new_y: int,
        heading: int,
        message_sender: MessageSender,
    ) -> None:
        """Teletransporta un jugador dentro del mismo mapa.

        Este método maneja el teletransporte cuando el jugador se mueve
        a una nueva posición dentro del mismo mapa (ej: comando GM /TELEP).

        Args:
            user_id: ID del jugador.
            map_id: ID del mapa (mismo origen y destino).
            old_x: Posición X anterior.
            old_y: Posición Y anterior.
            new_x: Nueva posición X.
            new_y: Nueva posición Y.
            heading: Dirección del jugador.
            message_sender: MessageSender del jugador.
        """
        # Obtener datos visuales del jugador
        visual_data = await self._get_player_visual_data(user_id)

        # 1. Actualizar posición en Redis
        await self.player_repo.set_position(user_id, new_x, new_y, map_id, heading)

        # 2. Actualizar índice espacial en MapManager
        self.map_manager.update_player_tile(user_id, map_id, old_x, old_y, new_x, new_y)

        # 3. Enviar POS_UPDATE al cliente
        await message_sender.send_pos_update(new_x, new_y)

        # 4. Broadcast CHARACTER_REMOVE en posición anterior
        await self.broadcast_service.broadcast_character_remove(map_id, user_id)

        # 5. Broadcast CHARACTER_CREATE en nueva posición
        await self.broadcast_service.broadcast_character_create(
            map_id=map_id,
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            heading=heading,
            x=new_x,
            y=new_y,
            name=visual_data.username,
        )

        logger.info(
            "Jugador %s (ID:%d) teletransportado en mapa %d: (%d,%d) -> (%d,%d)",
            visual_data.username,
            user_id,
            map_id,
            old_x,
            old_y,
            new_x,
            new_y,
        )

    async def _spawn_random_npcs_for_player(
        self, map_id: int, player_x: int, player_y: int, message_sender: MessageSender
    ) -> int:
        """Spawnea NPCs aleatorios para un jugador cuando entra en áreas designadas.

        Args:
            map_id: ID del mapa.
            player_x: Posición X del jugador.
            player_y: Posición Y del jugador.
            message_sender: MessageSender del jugador.

        Returns:
            Número de NPCs spawneados.
        """
        if not self.random_spawn_service:
            return 0

        # Spawneear NPCs aleatorios
        spawned_npcs = await self.random_spawn_service.spawn_random_npcs_for_player(
            map_id, player_x, player_y
        )

        # Enviar CHARACTER_CREATE de los NPCs spawneados al jugador
        for npc in spawned_npcs:
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
                fx=npc.fx_loop if hasattr(npc, "fx_loop") else 0,
                loops=-1 if hasattr(npc, "fx_loop") and npc.fx_loop > 0 else 0,
                name=npc.name,
            )
            await asyncio.sleep(0.01)

        if spawned_npcs:
            logger.debug(
                "Spawneados %d NPCs aleatorios para jugador en mapa %d pos (%d,%d)",
                len(spawned_npcs),
                map_id,
                player_x,
                player_y,
            )

        return len(spawned_npcs)
