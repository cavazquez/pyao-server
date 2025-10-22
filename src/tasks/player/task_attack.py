"""Task para manejar ataques de jugadores."""

import logging
from typing import TYPE_CHECKING

from src.packet_reader import PacketReader
from src.session_manager import SessionManager
from src.sounds import SoundID
from src.stamina_service import STAMINA_COST_ATTACK
from src.task import Task
from src.visual_effects import VisualEffectID

if TYPE_CHECKING:
    from src.combat_service import CombatService
    from src.item_catalog import ItemCatalog
    from src.loot_table_service import LootTableService
    from src.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.npc_death_service import NPCDeathService
    from src.npc_respawn_service import NPCRespawnService
    from src.npc_service import NPCService
    from src.player_repository import PlayerRepository
    from src.stamina_service import StaminaService

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
        npc_death_service: NPCDeathService | None = None,
        npc_respawn_service: NPCRespawnService | None = None,
        loot_table_service: LootTableService | None = None,
        item_catalog: ItemCatalog | None = None,
        stamina_service: StaminaService | None = None,
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
            npc_death_service: Servicio de muerte de NPCs.
            npc_respawn_service: Servicio de respawn de NPCs.
            loot_table_service: Servicio de loot tables.
            item_catalog: Catálogo de items.
            stamina_service: Servicio de stamina.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.combat_service = combat_service
        self.map_manager = map_manager
        self.npc_service = npc_service
        self.broadcast_service = broadcast_service
        self.npc_death_service = npc_death_service
        self.npc_respawn_service = npc_respawn_service
        self.loot_table_service = loot_table_service
        self.item_catalog = item_catalog
        self.stamina_service = stamina_service
        self.session_data = session_data or {}

    def _find_free_position_for_drop(
        self, map_id: int, center_x: int, center_y: int, radius: int = 2
    ) -> tuple[int, int] | None:
        """Busca una posición libre cercana para dropear un item.

        Args:
            map_id: ID del mapa.
            center_x: Coordenada X central.
            center_y: Coordenada Y central.
            radius: Radio de búsqueda.

        Returns:
            Tupla (x, y) con una posición libre, o None si no encuentra.
        """
        import random  # noqa: PLC0415

        if not self.map_manager:
            return None

        # Intentar primero la posición central (puede haber jugadores/NPCs)
        items = self.map_manager.get_ground_items(map_id, center_x, center_y)
        if not items:
            return (center_x, center_y)

        # Buscar en posiciones cercanas
        for _ in range(20):  # Máximo 20 intentos
            offset_x = random.randint(-radius, radius)  # noqa: S311
            offset_y = random.randint(-radius, radius)  # noqa: S311

            x = center_x + offset_x
            y = center_y + offset_y

            # Verificar límites del mapa
            if x < 1 or x > 100 or y < 1 or y > 100:  # noqa: PLR2004
                continue

            # Verificar que no haya otro item en esa posición
            items = self.map_manager.get_ground_items(map_id, x, y)
            if not items:
                return (x, y)

        return None

    async def execute(self) -> None:  # noqa: PLR0914, PLR0915
        """Procesa el ataque del jugador."""
        # Validar packet (no tiene datos, solo PacketID)
        _ = PacketReader(self.data)  # Valida que el packet sea válido

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

        # Consumir stamina por ataque
        if self.stamina_service:
            can_attack = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_ATTACK,
                message_sender=self.message_sender,
            )

            if not can_attack:
                logger.debug("user_id %d no tiene suficiente stamina para atacar", user_id)
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
        is_dodged = result.get("dodged", False)
        npc_died = result["npc_died"]

        # Si el NPC esquivó, mostrar mensaje y salir
        if is_dodged:
            await self.message_sender.send_console_msg(f"¡{target_npc.name} esquivó tu ataque!")
            await self.message_sender.send_create_fx(
                target_npc.char_index,
                VisualEffectID.MEDITATION,
                loops=1,  # Efecto de esquive
            )
            return

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

        # Si el NPC murió, usar servicio centralizado
        if npc_died:
            experience = result.get("experience", 0)

            # Usar NPCDeathService si está disponible
            if self.npc_death_service:
                await self.npc_death_service.handle_npc_death(
                    npc=target_npc,
                    killer_user_id=user_id,
                    experience=experience,
                    message_sender=self.message_sender,
                    death_reason="combate",
                )
            else:
                # Fallback: lógica antigua (para tests que no tienen el servicio)
                await self.message_sender.send_console_msg(
                    f"¡Has matado a {target_npc.name}! Ganaste {experience} EXP."
                )

                # Dropear items según loot table
                if self.loot_table_service and self.item_catalog:
                    loot = self.loot_table_service.get_loot_for_npc(target_npc.npc_id)

                    for item_id, quantity in loot:
                        # Obtener GrhIndex del catálogo
                        grh_index = self.item_catalog.get_grh_index(item_id)
                        if grh_index is None:
                            logger.warning("Item %d no tiene GrhIndex en el catálogo", item_id)
                            continue

                        logger.debug(
                            "Dropeando item_id=%d grh_index=%d quantity=%d",
                            item_id,
                            grh_index,
                            quantity,
                        )

                        # Buscar posición libre cercana para dropear el item
                        drop_pos = self._find_free_position_for_drop(
                            target_npc.map_id, target_npc.x, target_npc.y, radius=2
                        )

                        if not drop_pos:
                            logger.warning(
                                "No se encontró posición libre para dropear %s cerca de (%d,%d)",
                                self.item_catalog.get_item_name(item_id),
                                target_npc.x,
                                target_npc.y,
                            )
                            continue

                        drop_x, drop_y = drop_pos

                        # Crear ground item
                        ground_item: dict[str, int | str | None] = {
                            "item_id": item_id,
                            "quantity": quantity,
                            "grh_index": grh_index,
                            "owner_id": None,
                            "spawn_time": None,
                        }

                        # Agregar al MapManager
                        self.map_manager.add_ground_item(
                            map_id=target_npc.map_id, x=drop_x, y=drop_y, item=ground_item
                        )

                        # Broadcast OBJECT_CREATE a jugadores cercanos
                        if self.broadcast_service:
                            await self.broadcast_service.broadcast_object_create(
                                map_id=target_npc.map_id,
                                x=drop_x,
                                y=drop_y,
                                grh_index=grh_index,
                            )

                        item_name = self.item_catalog.get_item_name(item_id) or f"Item {item_id}"
                        logger.info(
                            "NPC %s dropeó %dx %s en (%d, %d)",
                            target_npc.name,
                            quantity,
                            item_name,
                            drop_x,
                            drop_y,
                        )

                # Remover NPC del mapa (esto también libera el tile en _tile_occupation)
                await self.npc_service.remove_npc(target_npc)

                # Programar respawn del NPC
                if self.npc_respawn_service:
                    await self.npc_respawn_service.schedule_respawn(target_npc)

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
