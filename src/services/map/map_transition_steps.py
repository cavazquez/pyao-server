"""Pasos modulares para la secuencia de transición de mapa."""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)


@dataclass
class MapTransitionContext:
    """Contexto para la transición de mapa."""

    user_id: int
    username: str
    char_body: int
    char_head: int
    current_map: int
    current_x: int
    current_y: int
    new_map: int
    new_x: int
    new_y: int
    heading: int
    message_sender: MessageSender


class MapTransitionStep(ABC):
    """Paso abstracto en la secuencia de transición de mapa."""

    @abstractmethod
    async def execute(self, context: MapTransitionContext) -> None:
        """Ejecuta el paso de transición."""


class SendChangeMapStep(MapTransitionStep):
    """Paso 1: Enviar CHANGE_MAP al cliente."""

    async def execute(self, context: MapTransitionContext) -> None:  # noqa: PLR6301
        """Envía el paquete CHANGE_MAP para que el cliente cargue el nuevo mapa."""
        logger.debug("Paso 1: Enviando CHANGE_MAP al mapa %d", context.new_map)
        await context.message_sender.send_change_map(context.new_map)


class ClientLoadDelayStep(MapTransitionStep):
    """Paso 2: Delay para que el cliente cargue el mapa."""

    def __init__(self, delay: float = 0.1) -> None:
        """Inicializa el paso con el delay especificado."""
        self.delay = delay

    async def execute(self, _context: MapTransitionContext) -> None:
        """Espera a que el cliente cargue el mapa."""
        logger.debug("Paso 2: Esperando %f segundos para carga del cliente", self.delay)
        await asyncio.sleep(self.delay)


class UpdatePositionStep(MapTransitionStep):
    """Paso 3: Actualizar posición en Redis."""

    def __init__(self, player_repo: PlayerRepository) -> None:
        """Inicializa el paso con el repositorio de jugadores."""
        self.player_repo = player_repo

    async def execute(self, context: MapTransitionContext) -> None:
        """Actualiza la posición del jugador en Redis."""
        logger.debug("Paso 3: Actualizando posición en Redis")
        await self.player_repo.set_position(
            context.user_id, context.new_x, context.new_y, context.new_map, context.heading
        )


class SendPositionUpdateStep(MapTransitionStep):
    """Paso 4: Enviar POS_UPDATE al cliente."""

    async def execute(self, context: MapTransitionContext) -> None:  # noqa: PLR6301
        """Envía la actualización de posición al cliente."""
        logger.debug("Paso 4: Enviando POS_UPDATE a (%d, %d)", context.new_x, context.new_y)
        await context.message_sender.send_pos_update(context.new_x, context.new_y)


class RemoveFromOldMapStep(MapTransitionStep):
    """Paso 5: Remover jugador del mapa anterior en MapManager."""

    def __init__(self, map_manager: MapManager) -> None:
        """Inicializa el paso con el gestor de mapas."""
        self.map_manager = map_manager

    async def execute(self, context: MapTransitionContext) -> None:
        """Remueve al jugador del mapa anterior."""
        logger.debug("Paso 5: Removiendo jugador del mapa %d", context.current_map)
        self.map_manager.remove_player(context.current_map, context.user_id)


class BroadcastRemoveFromOldMapStep(MapTransitionStep):
    """Paso 6: Broadcast CHARACTER_REMOVE en mapa anterior."""

    def __init__(self, broadcast_service: MultiplayerBroadcastService) -> None:
        """Inicializa el paso con el servicio de broadcast."""
        self.broadcast_service = broadcast_service

    async def execute(self, context: MapTransitionContext) -> None:
        """Envía broadcast de eliminación del jugador en el mapa anterior."""
        logger.debug("Paso 6: Broadcast CHARACTER_REMOVE en mapa %d", context.current_map)
        await self.broadcast_service.broadcast_character_remove(
            context.current_map, context.user_id
        )


class AddToNewMapStep(MapTransitionStep):
    """Paso 7: Agregar jugador al nuevo mapa en MapManager."""

    def __init__(self, map_manager: MapManager) -> None:
        """Inicializa el paso con el gestor de mapas."""
        self.map_manager = map_manager

    async def execute(self, context: MapTransitionContext) -> None:
        """Agrega al jugador al nuevo mapa."""
        logger.debug("Paso 7: Agregando jugador al mapa %d", context.new_map)
        self.map_manager.add_player(
            context.new_map, context.user_id, context.message_sender, context.username
        )


class SendSelfCharacterCreateStep(MapTransitionStep):
    """Paso 8: Enviar CHARACTER_CREATE del propio jugador."""

    async def execute(self, context: MapTransitionContext) -> None:  # noqa: PLR6301
        """Envía el CHARACTER_CREATE del propio jugador."""
        logger.debug("Paso 8: Enviando CHARACTER_CREATE propio")
        await context.message_sender.send_character_create(
            char_index=context.user_id,
            body=context.char_body,
            head=context.char_head,
            heading=context.heading,
            x=context.new_x,
            y=context.new_y,
            name=context.username,
        )


class SendExistingPlayersStep(MapTransitionStep):
    """Paso 9: Enviar todos los jugadores existentes en el nuevo mapa."""

    def __init__(
        self,
        send_players_in_map: Callable[[int, MessageSender, int | None], Awaitable[int]],
    ) -> None:
        """Inicializa el paso con la rutina de envío de jugadores."""
        self.send_players_in_map = send_players_in_map

    async def execute(self, context: MapTransitionContext) -> None:
        """Envía los jugadores existentes en el nuevo mapa."""
        logger.debug("Paso 9: Enviando jugadores existentes del mapa %d", context.new_map)
        await self.send_players_in_map(
            context.new_map,
            context.message_sender,
            context.user_id,
        )


class SendNPCsStep(MapTransitionStep):
    """Paso 10: Enviar todos los NPCs del nuevo mapa."""

    def __init__(
        self,
        send_npcs_in_map: Callable[[int, MessageSender], Awaitable[int]],
    ) -> None:
        """Inicializa el paso con la rutina de envío de NPCs."""
        self.send_npcs_in_map = send_npcs_in_map

    async def execute(self, context: MapTransitionContext) -> None:
        """Envía los NPCs del nuevo mapa."""
        logger.debug("Paso 10: Enviando NPCs del mapa %d", context.new_map)
        await self.send_npcs_in_map(context.new_map, context.message_sender)


class SendGroundItemsStep(MapTransitionStep):
    """Paso 11: Enviar todos los objetos del suelo en el nuevo mapa."""

    def __init__(
        self,
        send_ground_items_in_map: Callable[[int, MessageSender], Awaitable[int]],
    ) -> None:
        """Inicializa el paso con la rutina de envío de objetos."""
        self.send_ground_items_in_map = send_ground_items_in_map

    async def execute(self, context: MapTransitionContext) -> None:
        """Envía los objetos del suelo del nuevo mapa."""
        logger.debug("Paso 11: Enviando objetos del suelo del mapa %d", context.new_map)
        await self.send_ground_items_in_map(context.new_map, context.message_sender)


class BroadcastCreateInNewMapStep(MapTransitionStep):
    """Paso 12: Broadcast CHARACTER_CREATE del jugador a otros en el nuevo mapa."""

    def __init__(self, broadcast_service: MultiplayerBroadcastService) -> None:
        """Inicializa el paso con el servicio de broadcast."""
        self.broadcast_service = broadcast_service

    async def execute(self, context: MapTransitionContext) -> None:
        """Envía broadcast de creación del jugador en el nuevo mapa."""
        logger.debug("Paso 12: Broadcast CHARACTER_CREATE en mapa %d", context.new_map)
        await self.broadcast_service.broadcast_character_create(
            map_id=context.new_map,
            char_index=context.user_id,
            body=context.char_body,
            head=context.char_head,
            heading=context.heading,
            x=context.new_x,
            y=context.new_y,
            name=context.username,
        )


class MapTransitionOrchestrator:
    """Orquestador que ejecuta la secuencia de transición de mapa."""

    def __init__(self, steps: list[MapTransitionStep]) -> None:
        """Inicializa el orquestador con la lista de pasos."""
        self.steps = steps

    async def execute_transition(self, context: MapTransitionContext) -> None:
        """Ejecuta todos los pasos de la transición de mapa."""
        logger.info(
            "Iniciando transición de mapa para %s (ID:%d): %d -> %d",
            context.username,
            context.user_id,
            context.current_map,
            context.new_map,
        )

        for i, step in enumerate(self.steps, 1):
            try:
                await step.execute(context)
                logger.debug("Paso %d completado: %s", i, step.__class__.__name__)
            except Exception:
                logger.exception("Error en paso %d (%s)", i, step.__class__.__name__)
                raise

        logger.info(
            "Transición completada para %s (ID:%d): (%d,%d) -> (%d,%d)",
            context.username,
            context.user_id,
            context.current_x,
            context.current_y,
            context.new_x,
            context.new_y,
        )

    @classmethod
    def create_default_orchestrator(
        cls,
        player_repo: PlayerRepository,
        map_manager: MapManager,
        broadcast_service: MultiplayerBroadcastService,
        send_players_in_map: Callable[[int, MessageSender, int | None], Awaitable[int]],
        send_npcs_in_map: Callable[[int, MessageSender], Awaitable[int]],
        send_ground_items_in_map: Callable[[int, MessageSender], Awaitable[int]],
    ) -> MapTransitionOrchestrator:
        """Crea un orquestador con la secuencia predeterminada de 12 pasos.

        Returns:
            MapTransitionOrchestrator configurado con la secuencia estándar.
        """
        steps = [
            SendChangeMapStep(),
            ClientLoadDelayStep(),
            UpdatePositionStep(player_repo),
            SendPositionUpdateStep(),
            RemoveFromOldMapStep(map_manager),
            BroadcastRemoveFromOldMapStep(broadcast_service),
            AddToNewMapStep(map_manager),
            SendSelfCharacterCreateStep(),
            SendExistingPlayersStep(send_players_in_map),
            SendNPCsStep(send_npcs_in_map),
            SendGroundItemsStep(send_ground_items_in_map),
            BroadcastCreateInNewMapStep(broadcast_service),
        ]
        return cls(steps)
