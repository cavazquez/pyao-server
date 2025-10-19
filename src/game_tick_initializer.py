"""Inicializador del sistema de Game Tick y efectos."""

import logging
from typing import TYPE_CHECKING

from src.effect_gold_decay import GoldDecayEffect
from src.effect_hunger_thirst import HungerThirstEffect
from src.effect_npc_movement import NPCMovementEffect
from src.game_tick import GameTick
from src.meditation_effect import MeditationEffect
from src.npc_ai_effect import NPCAIEffect
from src.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.map_manager import MapManager
    from src.npc_ai_service import NPCAIService
    from src.npc_service import NPCService
    from src.player_repository import PlayerRepository
    from src.server_repository import ServerRepository

logger = logging.getLogger(__name__)


class GameTickInitializer:
    """Inicializa el sistema de Game Tick y sus efectos."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        server_repo: ServerRepository,
        map_manager: MapManager,
        npc_service: NPCService,
        npc_ai_service: NPCAIService,
    ) -> None:
        """Inicializa el inicializador de Game Tick.

        Args:
            player_repo: Repositorio de jugadores.
            server_repo: Repositorio del servidor.
            map_manager: Manager de mapas.
            npc_service: Servicio de NPCs.
            npc_ai_service: Servicio de IA de NPCs.
        """
        self.player_repo = player_repo
        self.server_repo = server_repo
        self.map_manager = map_manager
        self.npc_service = npc_service
        self.npc_ai_service = npc_ai_service

    async def initialize(self) -> GameTick:
        """Crea e inicializa el sistema de Game Tick con sus efectos.

        Returns:
            Sistema de Game Tick configurado.
        """
        logger.info("Inicializando sistema de Game Tick...")

        # Crear sistema de tick
        game_tick = GameTick(
            player_repo=self.player_repo,
            map_manager=self.map_manager,
            tick_interval=0.5,  # 0.5 segundos por tick
        )

        # Agregar efectos según configuración
        await self._add_effects(game_tick)

        logger.info("✓ Sistema de Game Tick inicializado")
        return game_tick

    async def _add_effects(self, game_tick: GameTick) -> None:
        """Agrega efectos al sistema de tick según configuración."""
        # Efecto de hambre y sed
        hunger_thirst_enabled = await self.server_repo.get_effect_config_bool(
            RedisKeys.CONFIG_HUNGER_THIRST_ENABLED, default=True
        )
        if hunger_thirst_enabled:
            game_tick.add_effect(HungerThirstEffect(self.server_repo))
            logger.info("✓ Efecto de hambre/sed habilitado")

        # Efecto de reducción de oro
        gold_decay_enabled = await self.server_repo.get_effect_config_bool(
            RedisKeys.CONFIG_GOLD_DECAY_ENABLED, default=True
        )
        if gold_decay_enabled:
            game_tick.add_effect(GoldDecayEffect(self.server_repo))
            logger.info("✓ Efecto de reducción de oro habilitado")

        # Efecto de meditación (siempre habilitado)
        game_tick.add_effect(MeditationEffect(interval_seconds=3.0))
        logger.info("✓ Efecto de meditación habilitado")

        # Efecto de movimiento de NPCs
        game_tick.add_effect(NPCMovementEffect(self.npc_service, interval_seconds=5.0))
        logger.info("✓ Efecto de movimiento de NPCs habilitado")

        # Efecto de IA de NPCs
        game_tick.add_effect(
            NPCAIEffect(self.npc_service, self.npc_ai_service, interval_seconds=2.0)
        )
        logger.info("✓ Efecto de IA de NPCs habilitado")
