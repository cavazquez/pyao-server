"""Handler para comando de click izquierdo en el mapa."""

import logging
import time
from typing import TYPE_CHECKING, cast

from src.command_handlers.left_click_npc_handler import LeftClickNPCHandler
from src.command_handlers.left_click_tile_handler import LeftClickTileHandler
from src.commands.base import Command, CommandHandler, CommandResult
from src.commands.left_click_command import LeftClickCommand
from src.config.config_manager import config_manager
from src.utils.redis_config import RedisKeys

TARGET_RANGE = 10

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.repositories.bank_repository import BankRepository
    from src.repositories.door_repository import DoorRepository
    from src.repositories.merchant_repository import MerchantRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.door_service import DoorService
    from src.services.map.map_resources_service import MapResourcesService
    from src.services.player.player_death_service import PlayerDeathService
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)


class LeftClickCommandHandler(CommandHandler):
    """Handler para comando de click izquierdo (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        map_manager: MapManager | None,
        map_resources: MapResourcesService | None,
        bank_repo: BankRepository | None,
        merchant_repo: MerchantRepository | None,
        door_service: DoorService | None,
        door_repo: DoorRepository | None,
        redis_client: RedisClient | None,
        message_sender: MessageSender,
        player_death_service: PlayerDeathService | None = None,
    ) -> None:
        """Inicializa el handler.

        Args:
            player_repo: Repositorio de jugadores.
            map_manager: Gestor de mapas para obtener NPCs.
            map_resources: Servicio de recursos del mapa.
            bank_repo: Repositorio de banco.
            merchant_repo: Repositorio de mercaderes.
            door_service: Servicio de puertas.
            door_repo: Repositorio de puertas.
            redis_client: Cliente Redis.
            message_sender: Enviador de mensajes.
            player_death_service: Operación compartida para los sacerdotes.
        """
        self.player_death_service = player_death_service
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.message_sender = message_sender

        # Inicializar handlers especializados
        self.npc_handler = LeftClickNPCHandler(
            merchant_repo=merchant_repo,
            bank_repo=bank_repo,
            redis_client=redis_client,
            message_sender=message_sender,
        )

        self.tile_handler = LeftClickTileHandler(
            map_manager=map_manager,
            map_resources=map_resources,
            door_service=door_service,
            door_repo=door_repo,
            message_sender=message_sender,
        )

    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando de click izquierdo (solo lógica de negocio).

        Args:
            command: Comando de click izquierdo.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, LeftClickCommand):
            return CommandResult.error("Comando inválido: se esperaba LeftClickCommand")

        user_id = command.user_id
        map_id = command.map_id
        x = command.x
        y = command.y

        logger.info(
            "LeftClickCommandHandler: user_id=%d hace click en mapa=%d, posición=(%d, %d)",
            user_id,
            map_id,
            x,
            y,
        )

        if not self.map_manager:
            logger.error("MapManager no disponible para click")
            return CommandResult.error("Error interno: gestor de mapas no disponible")

        try:
            position = await self.player_repo.get_position(user_id)
            if not position or position["map"] != map_id:
                return CommandResult.error("No puedes seleccionar objetivos de otro mapa.")
            target_key = f"chat:target:{user_id}"
            await self.player_repo.redis.redis.hset(
                target_key,
                mapping={
                    "npc": "",
                    "index": "0",
                    "user": "0",
                    "map": str(map_id),
                    "x": str(x),
                    "y": str(y),
                },
            )
            await self.player_repo.redis.redis.expire(target_key, 900)
            # Buscar NPC en esa posición
            npc_found = next(
                (
                    npc
                    for npc in self.map_manager.get_npcs_in_map(map_id)
                    if npc.x == x and npc.y == y
                ),
                None,
            )

            if npc_found:
                if max(abs(x - position["x"]), abs(y - position["y"])) > TARGET_RANGE:
                    return CommandResult.error("Estás demasiado lejos del NPC.")
                await self.player_repo.redis.redis.hset(
                    target_key,
                    mapping={"npc": npc_found.instance_id, "index": str(npc_found.char_index)},
                )
                priests = config_manager.get("game.spells.resurrection_npc_ids", [81, 82, 119])
                if (
                    command.double_click
                    and isinstance(priests, list)
                    and npc_found.npc_id in priests
                    and self.player_death_service
                ):
                    revived = await self.player_death_service.revive_player(
                        user_id, self.message_sender, priest=npc_found
                    )
                    return (
                        CommandResult.ok()
                        if revived
                        else CommandResult.error("No se pudo resucitar")
                    )
                success, error_msg, data = await self.npc_handler.handle_npc_click(
                    user_id, npc_found
                )
                if success:
                    return CommandResult.ok(data=data)
                return CommandResult.error(error_msg or "Error al procesar click en NPC")

            if max(
                abs(x - position["x"]), abs(y - position["y"])
            ) <= TARGET_RANGE and await self._select_player(user_id, map_id, x, y):
                return CommandResult.ok()
            # No hay NPC, mostrar información del tile
            success, error_msg, data = await self.tile_handler.handle_tile_click(map_id, x, y)
            if success:
                return CommandResult.ok(data=data)
            return CommandResult.error(error_msg or "Error al procesar click en tile")

        except Exception as e:
            logger.exception("Error procesando LEFT_CLICK")
            return CommandResult.error(f"Error al procesar click: {e!s}")

    async def _select_player(self, user_id: int, map_id: int, x: int, y: int) -> bool:
        """Selecciona un jugador visible y muestra su descripción sólo al observador.

        Returns:
            Si había un jugador y no corresponde mostrar información del terreno.
        """
        if self.map_manager is None:
            return False
        occupant = self.map_manager.get_tile_occupant(map_id, x, y)
        if not isinstance(occupant, str) or not occupant.startswith("player:"):
            return False
        target = int(occupant.split(":", 1)[1])
        if target == user_id:
            return False
        stats = cast(
            "dict[str, str]",
            await self.player_repo.redis.redis.hgetall(RedisKeys.player_user_stats(target)),
        )
        if any(
            float(stats.get(field, 0)) > time.time()
            for field in ("hidden_until", "invisible_until")
        ):
            return True
        await self.player_repo.redis.redis.hset(f"chat:target:{user_id}", "user", str(target))
        name = self.map_manager.get_player_username(target) or "Personaje"
        await self.message_sender.send_console_msg(
            name + (": " + stats["description"] if stats.get("description") else "")
        )
        return True
