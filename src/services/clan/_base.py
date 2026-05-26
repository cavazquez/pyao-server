"""Shared type declarations for clan service mixins."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.broadcast_service import BroadcastService
    from src.messaging.message_sender import MessageSender
    from src.repositories.clan_repository import ClanRepository
    from src.repositories.player_repository import PlayerRepository


class ClanServiceMixinBase:
    """Dependencies injected by ClanService.__init__."""

    clan_repo: ClanRepository
    player_repo: PlayerRepository
    message_sender: MessageSender
    broadcast_service: BroadcastService | None
    map_manager: MapManager | None
