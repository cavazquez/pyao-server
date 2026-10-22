"""Acciones de chat diferidas que conservan sus plazos e identidades en Redis."""

import time
from typing import TYPE_CHECKING

from src.effects.tick_effect import TickEffect
from src.services.classic_chat.admin_character import nearby
from src.services.classic_chat.context import ChatCommandError, ChatContext
from src.utils.redis_config import RedisKeys

JAIL_MAP = 66
WARNING_INTERVAL_SECONDS = 60

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender
    from src.repositories.player_repository import PlayerRepository


class ClassicActionsEffect(TickEffect):
    """Resuelve regreso al hogar y cancelación de descanso antes de regenerar energía."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Comparte las transiciones nativas y los repositorios del mundo."""
        self.deps = deps
        self.last_warning: dict[int, float] = {}
        self.prune_at = 0.0

    def get_name(self) -> str:
        """Identifica el efecto en métricas.

        Returns:
            Nombre estable del efecto.
        """
        return "ClassicActions"

    def get_interval_seconds(self) -> float:
        """Define la frecuencia del reloj de acciones diferidas.

        Returns:
            Un segundo.
        """
        return 1.0

    async def _jail(
        self, ctx: ChatContext, stats: dict[str, str], player_repo: PlayerRepository
    ) -> bool:
        """Completa traslados de cárcel pendientes o libera una condena vencida.

        Returns:
            Si debe esperar antes de procesar otras acciones del personaje.
        """
        user_id, key, message_sender = ctx.user, ctx.key, ctx.sender
        if (
            stats.get("jail_pending_return") == "1"
            and float(stats.get("jail_until", 0)) > time.time()
        ):
            position = await player_repo.get_position(user_id)
            if position and position["map"] != JAIL_MAP:
                try:
                    x, y = nearby(ctx, JAIL_MAP, 50, 50)
                except ChatCommandError:
                    return True
                await self.deps.player_map_service.transition_to_map(
                    user_id,
                    position["map"],
                    position["x"],
                    position["y"],
                    JAIL_MAP,
                    x,
                    y,
                    position.get("heading", 3),
                    message_sender,
                )
                return True
        if (
            stats.get("jail_pending_return") == "1"
            and float(stats.get("jail_until", 0)) <= time.time()
        ):
            position = await player_repo.get_position(user_id)
            if position and position["map"] == JAIL_MAP:
                map_id = int(stats.get("jail_return_map", 1))
                x, y = int(stats.get("jail_return_x", 50)), int(stats.get("jail_return_y", 50))
                try:
                    if not self.deps.map_manager.can_move_to(map_id, x, y):
                        x, y = nearby(ctx, map_id, x, y)
                except ChatCommandError:
                    map_id, x, y = 1, 50, 50
                    try:
                        x, y = nearby(ctx, map_id, x, y)
                    except ChatCommandError:
                        return True
                moved = await self.deps.player_map_service.transition_to_map(
                    user_id,
                    position["map"],
                    position["x"],
                    position["y"],
                    map_id,
                    x,
                    y,
                    position.get("heading", 3),
                    message_sender,
                )
                if not moved:
                    return True
                await ctx.tell("Tu condena terminó. Has sido liberado.")
            await ctx.redis.hset(key, "jail_pending_return", "0")
        return False

    async def apply(
        self, user_id: int, player_repo: PlayerRepository, message_sender: MessageSender | None
    ) -> None:
        """Aplica sólo los temporizadores activos del personaje conectado."""
        if message_sender is None:
            return
        key = RedisKeys.player_user_stats(user_id)
        stats = await player_repo.redis.hgetall(key)
        ctx = ChatContext(self.deps, user_id, message_sender, "/HOGAR", "")
        if time.time() >= self.prune_at:
            connected = set(self.deps.map_manager.get_all_connected_user_ids())
            self.last_warning = {
                user: at for user, at in self.last_warning.items() if user in connected
            }
            self.prune_at = time.time() + 60
        if await self._jail(ctx, stats, player_repo):
            return
        if stats.get("resting") == "1":
            position = await player_repo.get_position(user_id) or {}
            origin = (
                int(stats.get("rest_map", 0)),
                int(stats.get("rest_x", 0)),
                int(stats.get("rest_y", 0)),
            )
            valid = (position.get("map"), position.get("x"), position.get("y")) == origin and int(
                stats.get("min_hp", 0)
            ) > 0
            if valid:
                async with ctx.redis.pipeline(transaction=False) as pipe:
                    for dx in range(-1, 2):
                        for dy in range(-1, 2):
                            pipe.exists(
                                f"world:campfire:{origin[0]}:{origin[1] + dx}:{origin[2] + dy}"
                            )
                    valid = any(await pipe.execute())
            if not valid:
                await ctx.redis.hset(key, "resting", "0")
                await message_sender.status_effects.sync_status(user_id, player_repo)
        due = float(stats.get("home_due", 0))
        if due and int(stats.get("min_hp", 0)) > 0:
            await ctx.redis.hset(key, "home_due", "0")
        elif due and due <= time.time() and stats.get("death_state") == "complete":
            if float(stats.get("jail_until", 0)) > time.time():
                await ctx.redis.hset(key, "home_due", "0")
                return
            position = await player_repo.get_position(user_id) or {}
            if not position:
                return
            map_id, x, y = (
                int(stats.get("home_map", 1)),
                int(stats.get("home_x", 50)),
                int(stats.get("home_y", 50)),
            )
            try:
                if position["map"] != map_id:
                    if not self.deps.map_manager.can_move_to(map_id, x, y):
                        x, y = nearby(ctx, map_id, x, y)
                    moved = await self.deps.player_map_service.transition_to_map(
                        user_id=user_id,
                        current_map=position["map"],
                        current_x=position["x"],
                        current_y=position["y"],
                        new_map=map_id,
                        new_x=x,
                        new_y=y,
                        heading=position.get("heading", 3),
                        message_sender=message_sender,
                        home_deadline=due,
                    )
                    if not moved:
                        return
                await ctx.redis.hset(key, "home_due", "0")
                await ctx.tell("Has regresado a tu hogar.")
            except ChatCommandError:
                if time.time() - self.last_warning.get(user_id, 0) >= WARNING_INTERVAL_SECONDS:
                    await ctx.tell("Tu hogar no tiene una llegada libre; se reintentará.")
                    self.last_warning[user_id] = time.time()
