"""Task para manejar ataques de jugadores."""

import logging
from typing import TYPE_CHECKING

from src.item_constants import GOLD_GRH_INDEX, GOLD_ITEM_ID
from src.session_manager import SessionManager
from src.sounds import SoundID
from src.task import Task
from src.visual_effects import VisualEffectID

if TYPE_CHECKING:
    from src.combat_service import CombatService
    from src.map_manager import MapManager
    from src.message_sender import MessageSender
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.npc_service import NPCService
    from src.player_repository import PlayerRepository

logger = logging.getLogger(__name__)


class TaskAttack(Task):
    """Maneja el packet ATTACK del cliente."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository | None = None,
        combat_service: CombatService | None = None,
        map_manager: MapManager | None = None,
        npc_service: NPCService | None = None,
        broadcast_service: MultiplayerBroadcastService | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa el task.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            combat_service: Servicio de combate.
            map_manager: Gestor de mapas.
            npc_service: Servicio de NPCs.
            broadcast_service: Servicio de broadcast.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.combat_service = combat_service
        self.map_manager = map_manager
        self.npc_service = npc_service
        self.broadcast_service = broadcast_service
        self.session_data = session_data or {}

    async def execute(self) -> None:  # noqa: PLR0914, PLR0912, PLR0915, C901
        """Procesa el ataque del jugador."""
        # Obtener user_id de la sesión
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de atacar sin estar logueado")
            return

        # Validar que tenemos los servicios necesarios
        if (
            not self.player_repo
            or not self.combat_service
            or not self.map_manager
            or not self.npc_service
        ):
            logger.error("Dependencias no disponibles para atacar")
            return

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.error("No se encontró posición para user_id %d", user_id)
            return

        player_x = position["x"]
        player_y = position["y"]
        player_map = position["map"]
        player_heading = position["heading"]

        # Calcular posición del objetivo según la dirección
        target_x, target_y = self._get_target_position(player_x, player_y, player_heading)

        logger.debug(
            "Jugador %d ataca desde (%d,%d) hacia (%d,%d) en mapa %d",
            user_id,
            player_x,
            player_y,
            target_x,
            target_y,
            player_map,
        )

        # Buscar NPC en la posición objetivo
        target_npc = None
        all_npcs = self.map_manager.get_all_npcs()

        for npc in all_npcs:
            if npc.map_id == player_map and npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        if not target_npc:
            # No hay NPC en esa posición
            logger.debug("No hay NPC en posición (%d,%d)", target_x, target_y)
            await self.message_sender.send_console_msg("No hay nada que atacar ahí.")
            # Reproducir sonido de miss
            await self.message_sender.send_play_wave(SoundID.MISS, player_x, player_y)
            return

        # Verificar que el NPC sea atacable
        if not target_npc.is_attackable:
            await self.message_sender.send_console_msg(f"No puedes atacar a {target_npc.name}.")
            return

        # Realizar el ataque
        result = await self.combat_service.player_attack_npc(
            user_id, target_npc, self.message_sender
        )

        if not result:
            await self.message_sender.send_console_msg("No puedes atacar en este momento.")
            return

        damage = result["damage"]
        is_critical = result["critical"]
        npc_died = result["npc_died"]

        # Reproducir sonido de golpe
        await self.message_sender.send_play_wave(SoundID.SWORD_HIT, target_x, target_y)

        # Mostrar efecto visual
        if is_critical:
            await self.message_sender.send_create_fx(
                target_npc.char_index, VisualEffectID.CRITICAL_HIT, loops=1
            )
            await self.message_sender.send_console_msg(
                f"¡Golpe crítico! Le hiciste {damage} de daño a {target_npc.name}."
            )
        else:
            await self.message_sender.send_create_fx(
                target_npc.char_index, VisualEffectID.BLOOD, loops=1
            )
            await self.message_sender.send_console_msg(
                f"Le hiciste {damage} de daño a {target_npc.name}."
            )

        # Si el NPC murió
        if npc_died:
            experience = result.get("experience", 0)
            gold = result.get("gold", 0)

            await self.message_sender.send_console_msg(
                f"¡Has matado a {target_npc.name}! Ganaste {experience} EXP."
            )

            # Dropear oro en el suelo
            if gold > 0:
                ground_item = {
                    "item_id": GOLD_ITEM_ID,
                    "quantity": gold,
                    "grh_index": GOLD_GRH_INDEX,
                    "owner_id": None,
                    "spawn_time": None,
                }

                # Agregar al MapManager
                self.map_manager.add_ground_item(
                    map_id=target_npc.map_id, x=target_npc.x, y=target_npc.y, item=ground_item
                )

                # Broadcast OBJECT_CREATE a jugadores cercanos
                if self.broadcast_service:
                    await self.broadcast_service.broadcast_object_create(
                        map_id=target_npc.map_id,
                        x=target_npc.x,
                        y=target_npc.y,
                        grh_index=GOLD_GRH_INDEX,
                    )

                logger.info(
                    "NPC %s dropeó %d de oro en (%d, %d)",
                    target_npc.name,
                    gold,
                    target_npc.x,
                    target_npc.y,
                )

            # Remover NPC del mapa
            await self.npc_service.remove_npc(target_npc)

            # TODO: Dropear items según tabla de loot
            # TODO: Verificar si sube de nivel
        else:
            # Mostrar HP restante del NPC
            hp_percent = int((target_npc.hp / target_npc.max_hp) * 100)
            await self.message_sender.send_console_msg(
                f"{target_npc.name} tiene {target_npc.hp}/{target_npc.max_hp} HP ({hp_percent}%)."
            )

            # TODO: El NPC debería contraatacar

    def _get_target_position(  # noqa: PLR6301
        self, x: int, y: int, heading: int
    ) -> tuple[int, int]:
        """Calcula la posición objetivo según la dirección del jugador.

        Args:
            x: Posición X del jugador.
            y: Posición Y del jugador.
            heading: Dirección del jugador (1=Norte, 2=Este, 3=Sur, 4=Oeste).

        Returns:
            Tupla (target_x, target_y).
        """
        # Constantes de dirección
        north, east, south = 1, 2, 3

        if heading == north:
            return x, y - 1
        if heading == east:
            return x + 1, y
        if heading == south:
            return x, y + 1
        # heading == 4:  # Oeste
        return x - 1, y
