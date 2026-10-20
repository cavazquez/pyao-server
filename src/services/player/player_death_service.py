"""Orquestación del ciclo de vida; las pérdidas nunca se repiten por caller o reconexión."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from redis.exceptions import RedisError

from src.services.inventory_notifications import notify_inventory
from src.services.player.appearance import resolve_appearance
from src.services.player.lifecycle import resurrect, settle_death
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.npc import NPC
    from src.repositories.account_repository import AccountRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)
GHOST_BODY_MALE = 500
GHOST_HEAD = 500
DEATH_EXP_PENALTY_PERCENT = 0.05
DEATH_GOLD_DROP_PERCENT = 0.10
MAX_ITEMS_TO_DROP = 3
MIN_EXP_FOR_PENALTY = 100


class PlayerDeathService:
    """Mantiene tareas propias y publica únicamente el estado confirmado de una vida."""

    def __init__(
        self,
        map_manager: MapManager,
        player_repo: PlayerRepository,
        broadcast_service: MultiplayerBroadcastService,
        inventory_repo: InventoryRepository | None = None,
        item_catalog: ItemCatalog | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Recibe dependencias del mundo y conserva la propiedad de sus liquidaciones."""
        self.map_manager = map_manager
        self.player_repo = player_repo
        self.broadcast_service = broadcast_service
        self.inventory_repo = inventory_repo
        self.item_catalog = item_catalog
        self.account_repo = account_repo
        self._jobs: dict[int, asyncio.Task[None]] = {}
        self._closing = False

    def schedule_death(
        self,
        user_id: int,
        killer_name: str,
        death_reason: str = "combate",
        *,
        expected_life_id: int | None = None,
    ) -> None:
        """No espera AOF en el tick; una tarea propia resuelve toda la muerte en un commit."""
        if self._closing or user_id in self._jobs:
            return
        self._jobs[user_id] = asyncio.create_task(
            self._run_death(user_id, killer_name, death_reason, expected_life_id),
            name=f"death:{user_id}",
        )

    async def _run_death(
        self, user_id: int, killer_name: str, reason: str, life_id: int | None
    ) -> None:
        try:
            await self.handle_player_death(
                user_id, killer_name, death_reason=reason, expected_life_id=life_id
            )
        except RedisError, RuntimeError, ValueError:
            logger.exception(
                "Liquidación de muerte pendiente para jugador %d; se reintentará", user_id
            )
        finally:
            self._jobs.pop(user_id, None)

    async def handle_player_death(
        self,
        user_id: int,
        killer_name: str,
        message_sender: MessageSender | None = None,
        death_reason: str = "combate",
        *,
        expected_life_id: int | None = None,
    ) -> None:
        """Liquida una vida una sola vez, incluso tras perder ACK o reiniciar el proceso."""
        values = await self.player_repo.redis.hgetall(RedisKeys.player_user_stats(user_id))
        position = await self.player_repo.get_position(user_id)
        if not position or not values:
            return
        life_id = int(values.get("life_id", 0))
        if expected_life_id is not None and expected_life_id != life_id:
            return
        map_id, x, y = (
            int(values.get("death_map", position["map"])),
            int(values.get("death_x", position["x"])),
            int(values.get("death_y", position["y"])),
        )
        result = await self.map_manager.apply_ground_operation(
            map_id,
            x,
            y,
            self.player_repo.redis.redis,
            lambda: settle_death(self.player_repo.redis.redis, user_id, life_id, map_id, x, y),
            broadcast_service=self.broadcast_service,
        )
        if result["applied"]:
            await self.publish_state(user_id)
            sender = self.map_manager.get_player_message_sender(user_id)
            if sender is not None and (message_sender is None or sender is message_sender):
                await sender.send_console_msg(
                    f"Has muerto por {killer_name}. "
                    f"Perdiste {result['exp_loss']} puntos de experiencia."
                )
        logger.debug(
            "Muerte jugador=%d vida=%d causa=%s confirmada=%s",
            user_id,
            life_id,
            death_reason,
            result["applied"],
        )

    async def revive_player(
        self,
        user_id: int,
        message_sender: MessageSender,
        revive_at_spawn: bool = False,
        *,
        priest: NPC | None = None,
    ) -> bool:
        """Resucita en el lugar a media vida; no desplaza ni cobra a un vivo.

        Returns:
            Confirmación única; el parámetro legacy de spawn se rechaza explícitamente.
        """
        if revive_at_spawn:
            await message_sender.send_console_msg(
                "La resurrección de la 1.0 se realiza en el lugar."
            )
            return False
        # Adopta fantasmas antiguos sin volver a aplicarles penalizaciones históricas.
        values = await self.player_repo.redis.hgetall(RedisKeys.player_user_stats(user_id))
        if (
            int(values.get("min_hp", values.get("hp", 0))) <= 0
            and values.get("death_state") != "complete"
        ):
            await self.handle_player_death(user_id, "una vida anterior")
        result = await resurrect(
            self.player_repo.redis.redis, user_id, operation_id(), priest=priest
        )
        if not result["applied"]:
            await message_sender.send_console_msg(result["message"])
            return False
        await self.publish_state(user_id)
        await message_sender.send_console_msg("Has resucitado con la mitad de tu vida.")
        return True

    async def publish_state(self, user_id: int, *, refresh_inventory: bool = True) -> None:
        """Restaura apariencia/equipo/flags en todos los observadores y en el dueño actual.

        Args:
            user_id: Jugador cuyo estado confirmado se publica.
            refresh_inventory: Reenvía los slots salvo que el comando ya los haya enviado.
        """
        position = await self.player_repo.get_position(user_id)
        if not position:
            return
        stats = await self.player_repo.redis.hgetall(RedisKeys.player_user_stats(user_id))
        username = self.map_manager.get_player_username(user_id)
        account = (
            await self.account_repo.get_account(username)
            if self.account_repo and username
            else None
        )
        alive = int(stats.get("min_hp", stats.get("hp", 0))) > 0
        equipment = await self.player_repo.redis.hgetall(RedisKeys.player_equipment(user_id))
        inventory = await self.player_repo.redis.hgetall(RedisKeys.player_inventory(user_id))
        visual = resolve_appearance(account or {}, stats, equipment, inventory)
        for sender in self.map_manager.get_all_message_senders_in_map(position["map"]):
            await sender.send_character_change(
                user_id,
                body=visual.body,
                head=visual.head,
                heading=position.get("heading", 3),
                **visual.equipment(),
            )
            await sender.send_set_invisible(
                user_id,
                invisible=alive
                and max(float(stats.get("invisible_until", 0)), float(stats.get("hidden_until", 0)))
                > time.time(),
            )
        owner_sender = self.map_manager.get_player_message_sender(user_id)
        if owner_sender:
            await owner_sender.send_update_user_stats_from_repo(user_id, self.player_repo)
            await owner_sender.sync_status(user_id, self.player_repo)
            if self.inventory_repo and refresh_inventory:
                await notify_inventory(owner_sender, self.inventory_repo, user_id)

    async def close(self, deadline_seconds: float = 10) -> None:
        """Drena tareas propias antes de cerrar Redis; se puede repetir sin nuevos trabajos."""
        self._closing = True
        if not self._jobs:
            return
        tasks = tuple(self._jobs.values())
        _, pending = await asyncio.wait(tasks, timeout=deadline_seconds)
        for task in pending:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
