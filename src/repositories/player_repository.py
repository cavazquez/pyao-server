"""Repositorio para operaciones de jugadores usando Redis."""

from typing import TYPE_CHECKING

from src.repositories.player_mixins._attributes_mixin import PlayerAttributesMixin
from src.repositories.player_mixins._base import PlayerRepositoryBase
from src.repositories.player_mixins._position_mixin import PlayerPositionMixin
from src.repositories.player_mixins._skills_mixin import PlayerSkillsMixin
from src.repositories.player_mixins._stats_mixin import PlayerStatsMixin
from src.repositories.player_mixins._status_mixin import PlayerStatusMixin

if TYPE_CHECKING:
    from src.utils.redis_client import RedisClient
else:
    RedisClient = object


class PlayerRepository(
    PlayerRepositoryBase,
    PlayerPositionMixin,
    PlayerStatsMixin,
    PlayerAttributesMixin,
    PlayerStatusMixin,
    PlayerSkillsMixin,
):
    """Repositorio para operaciones de datos de jugadores."""

    def __init__(self, redis_client: RedisClient) -> None:
        """Inicializa el repositorio.

        Args:
            redis_client: Cliente Redis para operaciones de bajo nivel.
        """
        self.redis = redis_client
