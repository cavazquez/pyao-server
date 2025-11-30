"""Handler para comando de ataque."""

import logging
from typing import TYPE_CHECKING

from src.commands.attack_command import AttackCommand
from src.commands.base import Command, CommandHandler, CommandResult
from src.services.player.stamina_service import STAMINA_COST_ATTACK
from src.utils.sounds import SoundID
from src.utils.visual_effects import VisualEffectID

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.models.npc import NPC
    from src.repositories.player_repository import PlayerRepository
    from src.services.combat.combat_service import CombatService
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService
    from src.services.npc.loot_table_service import LootTableService
    from src.services.npc.npc_death_service import NPCDeathService
    from src.services.npc.npc_respawn_service import NPCRespawnService
    from src.services.npc.npc_service import NPCService
    from src.services.player.stamina_service import StaminaService

logger = logging.getLogger(__name__)


class AttackCommandHandler(CommandHandler):
    """Handler para comando de ataque (solo lógica de negocio)."""

    def __init__(
        self,
        player_repo: PlayerRepository,
        combat_service: CombatService,
        map_manager: MapManager,
        npc_service: NPCService,
        broadcast_service: MultiplayerBroadcastService | None,
        npc_death_service: NPCDeathService | None,
        npc_respawn_service: NPCRespawnService | None,
        loot_table_service: LootTableService | None,
        item_catalog: ItemCatalog | None,
        stamina_service: StaminaService | None,
        message_sender: MessageSender,
    ) -> None:
        """Inicializa el handler.

        Args:
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
            message_sender: Enviador de mensajes.
        """
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
        self.message_sender = message_sender

    async def handle(self, command: Command) -> CommandResult:  # noqa: PLR0914, PLR0915
        """Ejecuta el comando de ataque (solo lógica de negocio).

        Args:
            command: Comando de ataque.

        Returns:
            Resultado de la ejecución.
        """
        if not isinstance(command, AttackCommand):
            return CommandResult.error("Comando inválido: se esperaba AttackCommand")

        user_id = command.user_id
        target_x = command.target_x
        target_y = command.target_y
        map_id = command.map_id

        # Consumir stamina por ataque
        if self.stamina_service:
            can_attack = await self.stamina_service.consume_stamina(
                user_id=user_id,
                amount=STAMINA_COST_ATTACK,
                message_sender=self.message_sender,
            )

            if not can_attack:
                logger.debug("user_id %d no tiene suficiente stamina para atacar", user_id)
                return CommandResult.error("No tienes suficiente stamina para atacar.")

        # Obtener posición del jugador
        position = await self.player_repo.get_position(user_id)
        if not position:
            logger.error("No se encontró posición para user_id %d", user_id)
            return CommandResult.error("No se encontró posición del jugador.")

        player_x = position["x"]
        player_y = position["y"]

        logger.debug(
            "Jugador %d ataca desde (%d,%d) hacia (%d,%d) en mapa %d",
            user_id,
            player_x,
            player_y,
            target_x,
            target_y,
            map_id,
        )

        # Buscar NPC en la posición objetivo
        target_npc = None
        all_npcs = self.map_manager.get_all_npcs()

        for npc in all_npcs:
            if npc.map_id == map_id and npc.x == target_x and npc.y == target_y:
                target_npc = npc
                break

        if not target_npc:
            # No hay NPC en esa posición
            logger.debug("No hay NPC en posición (%d,%d)", target_x, target_y)
            await self.message_sender.send_console_msg("No hay nada que atacar ahí.")
            # Reproducir sonido de miss
            await self.message_sender.send_play_wave(SoundID.MISS, player_x, player_y)
            return CommandResult.error("No hay nada que atacar ahí.")

        # Verificar que el NPC sea atacable
        if not target_npc.is_attackable:
            await self.message_sender.send_console_msg(f"No puedes atacar a {target_npc.name}.")
            return CommandResult.error(f"No puedes atacar a {target_npc.name}.")

        # Realizar el ataque
        result = await self.combat_service.player_attack_npc(
            user_id, target_npc, self.message_sender
        )

        if not result:
            await self.message_sender.send_console_msg("No puedes atacar en este momento.")
            return CommandResult.error("No puedes atacar en este momento.")

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
            return CommandResult.ok({"dodged": True})

        # Reproducir sonido de golpe (sonido del atacante)
        await self.message_sender.send_play_wave(SoundID.SWORD_HIT, target_x, target_y)

        # Reproducir sonido de daño recibido del NPC (Snd2) si está disponible
        if target_npc.snd2 > 0 and self.broadcast_service:
            # Broadcast sonido a todos los jugadores en el mapa
            await self.broadcast_service.broadcast_play_wave(
                map_id=target_npc.map_id,
                wave_id=target_npc.snd2,
                x=target_npc.x,
                y=target_npc.y,
            )

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
                    await self._handle_loot_drop(target_npc)

                # Remover NPC del mapa
                await self.npc_service.remove_npc(target_npc)

                # Programar respawn del NPC
                if self.npc_respawn_service:
                    await self.npc_respawn_service.schedule_respawn(target_npc)

            return CommandResult.ok(
                {
                    "npc_died": True,
                    "damage": damage,
                    "experience": experience,
                    "npc_name": target_npc.name,
                }
            )

        # Mostrar HP restante del NPC
        hp_percent = int((target_npc.hp / target_npc.max_hp) * 100)
        await self.message_sender.send_console_msg(
            f"{target_npc.name} tiene {target_npc.hp}/{target_npc.max_hp} HP ({hp_percent}%)."
        )

        return CommandResult.ok(
            {
                "npc_died": False,
                "damage": damage,
                "npc_name": target_npc.name,
                "npc_hp": target_npc.hp,
                "npc_max_hp": target_npc.max_hp,
            }
        )

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

        # Intentar primero la posición central
        if self._is_valid_drop_position(map_id, center_x, center_y):
            return (center_x, center_y)

        # Buscar en posiciones cercanas
        for _ in range(20):  # Máximo 20 intentos
            offset_x = random.randint(-radius, radius)
            offset_y = random.randint(-radius, radius)

            # Saltar la posición central (ya la verificamos antes)
            if offset_x == 0 and offset_y == 0:
                continue

            x = center_x + offset_x
            y = center_y + offset_y

            # Verificar que sea posición válida
            if self._is_valid_drop_position(map_id, x, y):
                return (x, y)

        return None

    def _is_valid_drop_position(self, map_id: int, x: int, y: int) -> bool:
        """Verifica si una posición es válida para dropear items.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si la posición es válida para dropear.
        """
        if not self.map_manager:
            return False

        # Verificar límites del mapa
        if x < 1 or x > 100 or y < 1 or y > 100:  # noqa: PLR2004
            return False

        # Verificar que no haya items en esa posición
        items = self.map_manager.get_ground_items(map_id, x, y)
        if items:
            return False

        # Verificar que no haya un jugador o NPC ocupando el tile
        if self.map_manager.is_tile_occupied(map_id, x, y):
            return False

        # Verificar que la casilla no esté bloqueada (paredes, agua, etc.)
        return self.map_manager.can_move_to(map_id, x, y)

    async def _handle_loot_drop(self, npc: NPC) -> None:
        """Maneja el drop de loot cuando un NPC muere.

        Args:
            npc: NPC que murió.
        """
        if not self.loot_table_service or not self.item_catalog:
            return

        loot = self.loot_table_service.get_loot_for_npc(npc.npc_id)

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
            drop_pos = self._find_free_position_for_drop(npc.map_id, npc.x, npc.y, radius=2)

            if not drop_pos:
                logger.warning(
                    "No se encontró posición libre para dropear %s cerca de (%d,%d)",
                    self.item_catalog.get_item_name(item_id),
                    npc.x,
                    npc.y,
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
                map_id=npc.map_id, x=drop_x, y=drop_y, item=ground_item
            )

            # Broadcast OBJECT_CREATE a jugadores cercanos
            if self.broadcast_service:
                await self.broadcast_service.broadcast_object_create(
                    map_id=npc.map_id,
                    x=drop_x,
                    y=drop_y,
                    grh_index=grh_index,
                )

            item_name = self.item_catalog.get_item_name(item_id) or f"Item {item_id}"
            logger.info(
                "NPC %s dropeó %dx %s en (%d, %d)",
                npc.name,
                quantity,
                item_name,
                drop_x,
                drop_y,
            )
