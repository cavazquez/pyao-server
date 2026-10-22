"""Publicación administrativa de apariencia usando las capas canónicas del jugador."""

from typing import TYPE_CHECKING

from src.services.player.appearance import resolve_appearance
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.services.classic_chat.context import ChatContext


async def refresh_nameplate(ctx: ChatContext, user: int) -> None:
    """Reconstruye al actor para que todos los observadores reciban su etiqueta."""
    account = await ctx.deps.account_repo.get_account_by_user_id(user) or {}
    position = await ctx.deps.player_repo.get_position(user)
    if not position:
        return
    async with ctx.redis.pipeline(transaction=False) as pipe:
        pipe.hgetall(RedisKeys.player_user_stats(user))
        pipe.hgetall(RedisKeys.player_equipment(user))
        pipe.hgetall(RedisKeys.player_inventory(user))
        stats, equipment, inventory = await pipe.execute()
    visual = resolve_appearance(account, stats, equipment, inventory)
    for sender in ctx.deps.map_manager.get_all_message_senders_in_map(position["map"]):
        await sender.send_character_create(
            char_index=user,
            body=visual.body,
            head=visual.head,
            heading=position.get("heading", 3),
            x=position["x"],
            y=position["y"],
            name=account.get("username", str(user)),
            **visual.equipment(),
            show_name=stats.get("show_name", "1") != "0",
        )
    if ctx.deps.player_death_service:
        await ctx.deps.player_death_service.publish_state(user)
