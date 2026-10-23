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
    from src.services.map.door_world import DoorWorld
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.random_spawn_service import RandomSpawnService

from src.models.item_catalog import ItemCatalog
from src.services.map.map_transition_steps import (
    MapTransitionContext,
    MapTransitionOrchestrator,
)
from src.services.map.music import tracks as map_tracks
from src.services.map.transfer import commit_transfer
from src.services.player.appearance import resolve_appearance
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys

logger = logging.getLogger(__name__)
ENTITY_SEND_BATCH = 16


@dataclass
class PlayerVisualData:
    """Datos visuales de un jugador para CHARACTER_CREATE."""

    user_id: int
    username: str
    char_body: int
    char_head: int
    weapon: int = 0
    shield: int = 0
    helmet: int = 0
    show_name: bool = True
    boots: int = 0


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
        map_resources: MapResourcesService | None = None,
        door_world: DoorWorld | None = None,
    ) -> None:
        """Inicializa el servicio de mapas de jugador.

        Args:
            player_repo: Repositorio de jugadores.
            account_repo: Repositorio de cuentas.
            map_manager: Gestor de mapas.
            broadcast_service: Servicio de broadcast multijugador.
            random_spawn_service: Servicio de spawns aleatorios (opcional).
            map_resources: Talleres estáticos que se muestran al entrar (opcional).
            door_world: Estado compartido de puertas dinámicas.
        """
        self.player_repo = player_repo
        self.account_repo = account_repo
        self.map_manager = map_manager
        self.broadcast_service = broadcast_service
        self.random_spawn_service = random_spawn_service
        self.map_resources = map_resources
        self.door_world = door_world
        self._item_catalog = ItemCatalog()

        # Crear orquestador de transición con la secuencia predeterminada
        self.transition_orchestrator = MapTransitionOrchestrator.create_default_orchestrator(
            player_repo,
            map_manager,
            broadcast_service,
            self._send_players_in_map,
            self._send_npcs_in_map,
            self._send_ground_items_in_map,
            self._send_terrain_overrides,
        )

    async def _get_player_visual_data(
        self, user_id: int, *, sailing: bool | None = None
    ) -> PlayerVisualData:
        """Obtiene los datos visuales de un jugador (body, head, username).

        Args:
            user_id: ID del jugador.
            sailing: Medio confirmado para resolver la apariencia de llegada.

        Returns:
            PlayerVisualData con los datos del jugador.
        """
        account = await self.account_repo.get_account_by_user_id(user_id) or {}
        stats = await self.player_repo.redis.hgetall(RedisKeys.player_user_stats(user_id))
        if sailing is not None:
            stats["sailing"] = "1" if sailing else "0"
        equipment = await self.player_repo.redis.hgetall(RedisKeys.player_equipment(user_id))
        inventory = await self.player_repo.redis.hgetall(RedisKeys.player_inventory(user_id))
        visual = resolve_appearance(account, stats, equipment, inventory)
        return PlayerVisualData(
            user_id,
            account.get("username", f"Player{user_id}"),
            visual.body,
            visual.head,
            **visual.equipment(),
            show_name=stats.get("show_name", "1") != "0",
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
                weapon=other_visual.weapon,
                shield=other_visual.shield,
                helmet=other_visual.helmet,
                boots=other_visual.boots,
                heading=other_position.get("heading", 3),
                x=other_position["x"],
                y=other_position["y"],
                name=other_visual.username,
                show_name=other_visual.show_name,
            )
            players_sent += 1
            if players_sent % ENTITY_SEND_BATCH == 0:
                await asyncio.sleep(0)

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
                show_name=npc.show_name,
            )
            npcs_sent += 1
            if npcs_sent % ENTITY_SEND_BATCH == 0:
                await asyncio.sleep(0)

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
        items_sent = await self.map_manager.send_ground_items_snapshot(
            map_id, message_sender.send_object_create
        )
        if self.map_resources is not None:
            for x, y, graphic in self.map_resources.workshops.get(map_id, []):
                await message_sender.send_object_create(x, y, graphic)
                await message_sender.send_block_position(x, y, blocked=True)
                items_sent += 1

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
        for x, y in self.map_manager.get_exit_positions(map_id):
            if not self.map_manager.is_door_closed(map_id, x, y) and (
                self.map_resources is None or self.map_resources.is_blocked(map_id, x, y)
            ):
                # Enviar BLOCK_POSITION(false) para desbloquear el tile
                await message_sender.send_block_position(x, y, blocked=False)
                unblocked += 1
                if unblocked % ENTITY_SEND_BATCH == 0:
                    await asyncio.sleep(0)

        if unblocked > 0:
            logger.debug("Desbloqueados %d tiles de exit en mapa %d", unblocked, map_id)

        return unblocked

    async def _send_terrain_overrides(self, map_id: int, sender: MessageSender) -> int:
        """Sincroniza portales y puertas con la colisión efectiva del servidor.

        Returns:
            Cantidad de superposiciones enviadas.
        """
        count = await self._unblock_exit_tiles(map_id, sender)
        if self.door_world is not None:
            count += await self.door_world.snapshot(map_id, sender)
        music = self.map_manager.map_overrides.get(map_id, {}).get(
            "music", map_tracks().get(map_id, 0)
        )
        await sender.send_play_midi(int(music))
        for x, y in sorted(self.map_manager.overlay_positions.get(map_id, set())):
            state = self.map_manager.tile_overrides[map_id, x, y]
            if "blocked" in state:
                await sender.send_block_position(x, y, bool(state["blocked"]))
            if "portal" in state:
                if state["portal"]:
                    await sender.send_object_create(
                        x, y, self._item_catalog.get_grh_index(651) or 0
                    )
                else:
                    await sender.send_object_delete(x, y)
            count += 1
        return count

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

        # Excepciones del terreno antes del primer actor/input del cliente.
        await self._send_terrain_overrides(map_id, message_sender)

        # 2. Enviar CHARACTER_CREATE del propio jugador
        await message_sender.send_character_create(
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            weapon=visual_data.weapon,
            shield=visual_data.shield,
            helmet=visual_data.helmet,
            boots=visual_data.boots,
            heading=heading,
            x=x,
            y=y,
            name=visual_data.username,
            show_name=visual_data.show_name,
        )

        # 3. Enviar todos los jugadores existentes en el mapa
        await self._send_players_in_map(map_id, message_sender, exclude_user_id=user_id)

        # 4. Enviar todos los NPCs del mapa
        await self._send_npcs_in_map(map_id, message_sender)

        # 4b. Spawneear NPCs aleatorios si hay áreas configuradas
        await self._spawn_random_npcs_for_player(map_id, x, y, message_sender)

        # 5. Enviar todos los ground items del mapa
        await self._send_ground_items_in_map(map_id, message_sender)

        # 7. Broadcast CHARACTER_CREATE a otros jugadores
        await self.broadcast_service.broadcast_character_create(
            map_id=map_id,
            char_index=user_id,
            body=visual_data.char_body,
            head=visual_data.char_head,
            weapon=visual_data.weapon,
            shield=visual_data.shield,
            helmet=visual_data.helmet,
            boots=visual_data.boots,
            heading=heading,
            x=x,
            y=y,
            name=visual_data.username,
        )

        await self._sync_map_states(map_id)
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
        *,
        home_deadline: float | None = None,
    ) -> bool:
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
            home_deadline: Plazo observado de regreso al hogar, si es un fantasma.

        Returns:
            Si se confirmó el destino conservando las validaciones de llegada.

        Raises:
            asyncio.CancelledError: Si se cancela la conexión durante la publicación.
        """
        if not self.map_manager.has_map(new_map):
            return await self._reject_arrival(
                message_sender, current_x, current_y, "El mapa de destino no existe."
            )
        water = bool(self.map_resources and self.map_resources.has_water(new_map, new_x, new_y))
        if self.map_resources and (
            (self.map_resources.is_blocked(new_map, new_x, new_y) and not water)
            or self.map_resources.has_tree(new_map, new_x, new_y)
            or self.map_resources.has_mine(new_map, new_x, new_y)
        ):
            return await self._reject_arrival(
                message_sender, current_x, current_y, "La llegada está bloqueada."
            )
        visual_data = await self._get_player_visual_data(user_id, sailing=water)
        identity = operation_id()
        if not self.map_manager.reserve_arrival(identity, new_map, new_x, new_y, water=water):
            return await self._reject_arrival(
                message_sender, current_x, current_y, "La llegada está ocupada o bloqueada."
            )
        try:
            result = await commit_transfer(
                self.player_repo,
                self._item_catalog,
                user_id,
                (current_map, current_x, current_y),
                (new_map, new_x, new_y),
                heading,
                water,
                identity,
                home_deadline=home_deadline,
            )
            if not result["applied"]:
                return await self._reject_arrival(
                    message_sender, current_x, current_y, str(result["message"])
                )
            if result["dead"]:
                visual_data.char_body, visual_data.char_head = 500, 500
                visual_data.weapon = visual_data.shield = visual_data.helmet = visual_data.boots = 0
            try:
                await self._complete_transfer(
                    user_id,
                    current_map,
                    current_x,
                    current_y,
                    new_map,
                    new_x,
                    new_y,
                    heading,
                    message_sender,
                    visual_data,
                    bool(result["navigation_changed"]),
                )
            except OSError:
                # El commit ya tiene destino e índice coherentes. Una reconexión
                # reconstruye ese snapshot; volver al origen podría pisar a otro.
                logger.warning("Conexión interrumpida tras confirmar transición de %d", user_id)
                await self._disconnect_committed_arrival(user_id, current_map, message_sender)
            except asyncio.CancelledError:
                await self._disconnect_committed_arrival(user_id, current_map, message_sender)
                raise
            return True
        finally:
            self.map_manager.release_positions(identity, (new_map, new_x, new_y))

    async def _disconnect_committed_arrival(
        self, user_id: int, old_map: int, sender: MessageSender
    ) -> None:
        """Retira la imagen anterior aunque falle el primer paquete del mapa nuevo."""
        try:
            await self.broadcast_service.broadcast_character_remove(old_map, user_id)
        except OSError:
            logger.warning("Un observador desconectado no recibió la retirada de %d", user_id)
        finally:
            sender.connection.close()

    @staticmethod
    async def _reject_arrival(message_sender: MessageSender, x: int, y: int, message: str) -> bool:
        """Resincroniza la predicción local sin cambiar Redis ni la pertenencia al mapa.

        Returns:
            False para que WALK nunca informe una transición rechazada como exitosa.
        """
        await message_sender.send_console_msg(message)
        await message_sender.send_pos_update(x, y)
        return False

    async def _complete_transfer(
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
        visual_data: PlayerVisualData,
        navigation_changed: bool,
    ) -> None:
        """Tras el commit, publica el destino autoritativo y los snapshots del mapa."""
        if current_map == new_map:
            self.map_manager.update_player_tile(
                user_id, new_map, current_x, current_y, new_x, new_y
            )
            if navigation_changed:
                await message_sender.send_navigate_toggle()
            await message_sender.send_pos_update(new_x, new_y)
            await self.broadcast_service.broadcast_character_remove(new_map, user_id)
            await self.broadcast_service.broadcast_character_create(
                map_id=new_map,
                char_index=user_id,
                body=visual_data.char_body,
                head=visual_data.char_head,
                weapon=visual_data.weapon,
                shield=visual_data.shield,
                helmet=visual_data.helmet,
                boots=visual_data.boots,
                heading=heading,
                x=new_x,
                y=new_y,
                name=visual_data.username,
            )
            await self._sync_map_states(new_map)
            return

        # Crear contexto de transición
        context = MapTransitionContext(
            user_id=user_id,
            username=visual_data.username,
            char_body=visual_data.char_body,
            char_head=visual_data.char_head,
            show_name=visual_data.show_name,
            weapon=visual_data.weapon,
            shield=visual_data.shield,
            helmet=visual_data.helmet,
            boots=visual_data.boots,
            current_map=current_map,
            current_x=current_x,
            current_y=current_y,
            new_map=new_map,
            new_x=new_x,
            new_y=new_y,
            heading=heading,
            message_sender=message_sender,
            position_committed=True,
            navigation_changed=navigation_changed,
        )

        # Ejecutar transición usando el orquestador
        await self.transition_orchestrator.execute_transition(context)

        # Spawneear NPCs aleatorios después de la transición (si hay áreas configuradas)
        await self._spawn_random_npcs_for_player(new_map, new_x, new_y, message_sender)
        await self._sync_map_states(new_map)

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
    ) -> bool:
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

        Returns:
            Si se confirmó el destino conservando las validaciones de llegada.
        """
        return await self.transition_to_map(
            user_id, map_id, old_x, old_y, map_id, new_x, new_y, heading, message_sender
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
        for index, npc in enumerate(spawned_npcs, start=1):
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
                show_name=npc.show_name,
            )
            if index % ENTITY_SEND_BATCH == 0:
                await asyncio.sleep(0)

        if spawned_npcs:
            logger.debug(
                "Spawneados %d NPCs aleatorios para jugador en mapa %d pos (%d,%d)",
                len(spawned_npcs),
                map_id,
                player_x,
                player_y,
            )

        return len(spawned_npcs)

    async def _sync_map_states(self, map_id: int) -> None:
        for viewer in self.map_manager.get_players_in_map(map_id):
            sender = self.map_manager.get_player_message_sender(viewer)
            if sender:
                await sender.status_effects.sync_visibility(
                    viewer, self.player_repo, self.map_manager
                )
                await sender.status_effects.sync_campfires(viewer, self.player_repo)
                await sender.sync_status(viewer, self.player_repo)
