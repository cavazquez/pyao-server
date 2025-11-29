"""Inicializador del sistema de Game Tick y efectos."""

import logging
from typing import TYPE_CHECKING

from src.effects.effect_attribute_modifiers import AttributeModifiersEffect
from src.effects.effect_gold_decay import GoldDecayEffect
from src.effects.effect_hunger_thirst import HungerThirstEffect
from src.effects.effect_npc_movement import NPCMovementEffect
from src.effects.effect_npc_poison import NPCPoisonEffect
from src.effects.effect_poison import PoisonEffect
from src.effects.effect_stamina_regen import StaminaRegenEffect
from src.effects.meditation_effect import MeditationEffect
from src.effects.npc_ai_effect import NPCAIEffect
from src.game.game_tick import GameTick
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.repositories.player_repository import PlayerRepository
    from src.repositories.server_repository import ServerRepository
    from src.services.npc.npc_ai_service import NPCAIService
    from src.services.npc.npc_service import NPCService
    from src.services.player.stamina_service import StaminaService

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
        stamina_service: StaminaService,
    ) -> None:
        """Inicializa el inicializador de Game Tick.

        Args:
            player_repo: Repositorio de jugadores.
            server_repo: Repositorio del servidor.
            map_manager: Manager de mapas.
            npc_service: Servicio de NPCs.
            npc_ai_service: Servicio de IA de NPCs.
            stamina_service: Servicio de stamina.
        """
        self.player_repo = player_repo
        self.server_repo = server_repo
        self.map_manager = map_manager
        self.npc_service = npc_service
        self.npc_ai_service = npc_ai_service
        self.stamina_service = stamina_service

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
        # Intervalo aumentado a 3.5s para evitar spam de ataques con múltiples NPCs
        game_tick.add_effect(
            NPCAIEffect(self.npc_service, self.npc_ai_service, interval_seconds=3.5)
        )
        logger.info("✓ Efecto de IA de NPCs habilitado (intervalo: 3.5s)")

        # Efecto de regeneración de stamina (siempre habilitado)
        game_tick.add_effect(StaminaRegenEffect(self.stamina_service))
        logger.info("✓ Efecto de regeneración de stamina habilitado")

        # Efecto de envenenamiento para jugadores (siempre habilitado)
        game_tick.add_effect(PoisonEffect(interval_seconds=2.0))
        logger.info("✓ Efecto de envenenamiento (jugadores) habilitado")

        # Efecto de envenenamiento para NPCs (siempre habilitado)
        game_tick.add_effect(NPCPoisonEffect(self.npc_service, interval_seconds=2.0))
        logger.info("✓ Efecto de envenenamiento (NPCs) habilitado")

        # Efecto de limpieza de modificadores de atributos (siempre habilitado)
        game_tick.add_effect(AttributeModifiersEffect(interval_seconds=10.0))
        logger.info("✓ Efecto de limpieza de modificadores de atributos habilitado")
