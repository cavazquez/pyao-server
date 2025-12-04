"""Base classes para el sistema de efectos de hechizos (Strategy Pattern)."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.models.spell_catalog import SpellCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.npc_repository import NPCRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_service import NPCService
    from src.services.npc.summon_service import SummonService

logger = logging.getLogger(__name__)


@dataclass
class SpellContext:
    """Contexto compartido para la ejecución de efectos de hechizos."""

    # Datos del caster
    user_id: int
    caster_stats: dict[str, Any]
    caster_position: dict[str, Any]

    # Datos del hechizo
    spell_id: int
    spell_data: dict[str, Any]
    spell_name: str

    # Datos del target
    target_x: int
    target_y: int
    target_npc: NPC | None = None
    target_player_id: int | None = None
    target_player_stats: dict[str, Any] | None = None

    # Daño/curación calculado
    base_amount: int = 0
    total_amount: int = 0

    # Estado del efecto
    npc_died: bool = False

    # Comunicación
    message_sender: MessageSender | None = None

    # Servicios inyectados
    player_repo: PlayerRepository | None = None
    npc_repo: NPCRepository | None = None
    account_repo: AccountRepository | None = None
    map_manager: MapManager | None = None
    broadcast_service: MultiplayerBroadcastService | None = None
    npc_service: NPCService | None = None
    npc_death_service: NPCDeathService | None = None
    summon_service: SummonService | None = None
    spell_catalog: SpellCatalog | None = None

    @property
    def target_name(self) -> str:
        """Obtiene el nombre del target."""
        if self.target_npc:
            return self.target_npc.name
        if self.target_player_id:
            if self.target_player_id == self.user_id:
                return "tí mismo"
            if self.map_manager:
                return (
                    self.map_manager.get_player_username(self.target_player_id)
                    or f"Jugador {self.target_player_id}"
                )
            return f"Jugador {self.target_player_id}"
        return "objetivo"

    @property
    def is_self_cast(self) -> bool:
        """Verifica si es auto-cast."""
        return self.target_player_id == self.user_id

    @property
    def map_id(self) -> int:
        """Obtiene el ID del mapa actual."""
        return self.caster_position.get("map", 1)

    async def get_target_message_sender(self) -> MessageSender | None:
        """Obtiene el MessageSender del target (si es un jugador).

        Returns:
            MessageSender del target o None si no hay target válido.
        """
        if not self.target_player_id or not self.map_manager:
            return None
        if self.target_player_id == self.user_id:
            return self.message_sender
        return self.map_manager.get_player_message_sender(self.target_player_id)


@dataclass
class SpellEffectResult:
    """Resultado de aplicar un efecto de hechizo."""

    success: bool = True
    stop_processing: bool = False  # Si True, no procesar más efectos
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


class SpellEffect(ABC):
    """Interfaz base para efectos de hechizos (Strategy Pattern)."""

    @abstractmethod
    def can_apply(self, ctx: SpellContext) -> bool:
        """Verifica si este efecto debe aplicarse según spell_data.

        Args:
            ctx: Contexto del hechizo.

        Returns:
            True si el efecto debe aplicarse.
        """

    @abstractmethod
    async def apply_to_npc(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica el efecto a un NPC.

        Args:
            ctx: Contexto del hechizo.

        Returns:
            Resultado del efecto.
        """

    @abstractmethod
    async def apply_to_player(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica el efecto a un jugador.

        Args:
            ctx: Contexto del hechizo.

        Returns:
            Resultado del efecto.
        """

    async def apply(self, ctx: SpellContext) -> SpellEffectResult:
        """Aplica el efecto al target apropiado.

        Args:
            ctx: Contexto del hechizo.

        Returns:
            Resultado del efecto.
        """
        if ctx.target_npc:
            return await self.apply_to_npc(ctx)
        if ctx.target_player_id:
            return await self.apply_to_player(ctx)
        return SpellEffectResult(success=False, message="No hay target válido")
