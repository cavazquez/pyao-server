"""Servicio para manejar la muerte de jugadores."""

import logging
import random
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.item_catalog import ItemCatalog
    from src.repositories.account_repository import AccountRepository
    from src.repositories.inventory_repository import InventoryRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.multiplayer_broadcast_service import MultiplayerBroadcastService

logger = logging.getLogger(__name__)

# Constantes de fantasma (IDs de body/head cuando el jugador está muerto)
GHOST_BODY_MALE = 500  # Body de fantasma masculino
GHOST_BODY_FEMALE = 501  # Body de fantasma femenino
GHOST_HEAD = 500  # Head de fantasma (sin rostro)
MALE_BODY_THRESHOLD = 50  # Bodies < 50 son masculinos, >= 50 son femeninos

# Constantes de penalización
DEATH_EXP_PENALTY_PERCENT = 0.05  # 5% de pérdida de experiencia al morir
DEATH_GOLD_DROP_PERCENT = 0.10  # 10% del oro se dropea al morir
MAX_ITEMS_TO_DROP = 3  # Máximo de items que puede perder al morir
MIN_EXP_FOR_PENALTY = 100  # Experiencia mínima para aplicar penalización

# Puntos de respawn por defecto (ciudad segura)
DEFAULT_RESPAWN_MAP = 1
DEFAULT_RESPAWN_X = 50
DEFAULT_RESPAWN_Y = 50


class PlayerDeathService:
    """Servicio centralizado para manejar la muerte de jugadores."""

    def __init__(
        self,
        map_manager: MapManager,
        player_repo: PlayerRepository,
        broadcast_service: MultiplayerBroadcastService,
        inventory_repo: InventoryRepository | None = None,
        item_catalog: ItemCatalog | None = None,
        account_repo: AccountRepository | None = None,
    ) -> None:
        """Inicializa el servicio de muerte de jugadores.

        Args:
            map_manager: Gestor de mapas.
            player_repo: Repositorio de jugadores.
            broadcast_service: Servicio de broadcast.
            inventory_repo: Repositorio de inventario (opcional).
            item_catalog: Catálogo de items (opcional).
            account_repo: Repositorio de cuentas (opcional).
        """
        self.map_manager = map_manager
        self.player_repo = player_repo
        self.broadcast_service = broadcast_service
        self.inventory_repo = inventory_repo
        self.item_catalog = item_catalog
        self.account_repo = account_repo

    async def handle_player_death(
        self,
        user_id: int,
        killer_name: str,
        message_sender: MessageSender,
        death_reason: str = "combate",
    ) -> None:
        """Maneja completamente la muerte de un jugador.

        Args:
            user_id: ID del jugador que murió.
            killer_name: Nombre del asesino (NPC o jugador).
            message_sender: MessageSender del jugador.
            death_reason: Razón de la muerte ("combate", "hechizo", "veneno", etc).
        """
        logger.info(
            "Jugador %d murió por %s (%s). Procesando muerte...",
            user_id,
            killer_name,
            death_reason,
        )

        # Obtener datos del jugador
        position = await self.player_repo.get_position(user_id)
        stats = await self.player_repo.get_stats(user_id)

        if not position or not stats:
            logger.error(
                "No se pudieron obtener datos del jugador %d para procesar muerte", user_id
            )
            return

        map_id = position["map"]
        x = position["x"]
        y = position["y"]

        # 1. Aplicar penalización de experiencia
        await self._apply_exp_penalty(user_id, stats, message_sender)

        # 2. Dropear oro en el suelo
        await self._drop_gold(user_id, map_id, x, y, stats)

        # 3. Dropear algunos items del inventario (aleatorio)
        await self._drop_random_items(user_id, map_id, x, y)

        # 4. Convertir en fantasma (cambiar apariencia usando sistema de morph)
        await self._convert_to_ghost(user_id)

        # 5. Enviar mensaje de muerte
        await message_sender.send_console_msg(
            f"¡Has sido asesinado por {killer_name}!",
            font_color=6,  # FONTTYPE_FIGHT (rojo)
        )

        # 6. Teletransportar a punto de respawn (opcional - puede esperar a que resucite)
        # Por ahora dejamos al jugador como fantasma donde murió
        # El jugador deberá buscar un sacerdote para resucitar

        logger.info(
            "Jugador %d procesado como muerto. Convertido en fantasma en (%d,%d)",
            user_id,
            x,
            y,
        )

    async def revive_player(
        self,
        user_id: int,
        message_sender: MessageSender,
        revive_at_spawn: bool = True,
    ) -> bool:
        """Revive a un jugador muerto.

        Args:
            user_id: ID del jugador a revivir.
            message_sender: MessageSender del jugador.
            revive_at_spawn: Si True, teletransporta al punto de respawn.

        Returns:
            True si se revivió exitosamente.
        """
        stats = await self.player_repo.get_stats(user_id)

        if not stats:
            return False

        # Verificar si está muerto (HP = 0)
        if stats.get("min_hp", 0) > 0:
            await message_sender.send_console_msg("No estás muerto.")
            return False

        # Restaurar HP (50% del máximo al revivir)
        max_hp = stats.get("max_hp", 100)
        revive_hp = max_hp // 2

        await self.player_repo.update_hp(user_id, revive_hp)

        # Restaurar apariencia original eliminando el morph de fantasma
        # Ponemos morphed_until en 0 para que el sistema use la apariencia original
        await self.player_repo.set_morphed_appearance(
            user_id,
            morphed_body=0,
            morphed_head=0,
            morphed_until=0.0,
        )

        # El broadcast del cambio de apariencia se hará automáticamente
        # cuando el cliente se reconecte o el sistema de broadcast actualice

        # Teletransportar a spawn si es necesario
        if revive_at_spawn:
            await self._teleport_to_spawn(user_id)

        # Actualizar stats del cliente
        stats = await self.player_repo.get_stats(user_id)
        if stats:
            await message_sender.send_update_user_stats(
                max_hp=stats.get("max_hp", 100),
                min_hp=revive_hp,
                max_mana=stats.get("max_mana", 100),
                min_mana=stats.get("min_mana", 100),
                max_sta=stats.get("max_sta", 100),
                min_sta=stats.get("min_sta", 100),
                gold=stats.get("gold", 0),
                level=stats.get("level", 1),
                elu=stats.get("elu", 300),
                experience=stats.get("experience", 0),
            )

        await message_sender.send_console_msg(
            "Has resucitado.",
            font_color=14,  # FONTTYPE_INFO (dorado)
        )

        logger.info("Jugador %d revivido con %d HP", user_id, revive_hp)
        return True

    async def _apply_exp_penalty(
        self,
        user_id: int,
        stats: dict[str, int],
        message_sender: MessageSender,
    ) -> None:
        """Aplica penalización de experiencia por morir.

        Args:
            user_id: ID del jugador.
            stats: Stats actuales del jugador.
            message_sender: MessageSender del jugador.
        """
        current_exp = stats.get("experience", 0)

        # No penalizar si tiene muy poca experiencia
        if current_exp < MIN_EXP_FOR_PENALTY:
            return

        # Calcular penalización
        exp_loss = int(current_exp * DEATH_EXP_PENALTY_PERCENT)
        new_exp = max(0, current_exp - exp_loss)

        # Actualizar experiencia
        await self.player_repo.update_experience(user_id, new_exp)

        # Notificar al jugador
        await message_sender.send_console_msg(
            f"Perdiste {exp_loss} puntos de experiencia.",
            font_color=6,  # FONTTYPE_FIGHT
        )
        await message_sender.send_update_exp(new_exp)

        logger.info("Jugador %d perdió %d EXP por morir (tenía %d)", user_id, exp_loss, current_exp)

    async def _drop_gold(
        self,
        user_id: int,
        map_id: int,
        x: int,
        y: int,
        stats: dict[str, int],
    ) -> None:
        """Dropea oro del jugador muerto en el suelo.

        Args:
            user_id: ID del jugador.
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
            stats: Stats del jugador.
        """
        current_gold = stats.get("gold", 0)

        if current_gold <= 0:
            return

        # Calcular oro a dropear
        gold_to_drop = int(current_gold * DEATH_GOLD_DROP_PERCENT)
        if gold_to_drop <= 0:
            return

        # Reducir oro del jugador
        new_gold = current_gold - gold_to_drop
        await self.player_repo.update_gold(user_id, new_gold)

        # Crear ground item de oro
        gold_item: dict[str, int | str | None] = {
            "item_id": 12,  # ID del oro
            "quantity": gold_to_drop,
            "grh_index": 511,  # GrhIndex del oro
            "owner_id": None,  # Cualquiera puede recoger
            "spawn_time": None,
        }

        # Agregar al mapa
        self.map_manager.add_ground_item(map_id=map_id, x=x, y=y, item=gold_item)

        # Broadcast a jugadores cercanos
        await self.broadcast_service.broadcast_object_create(
            map_id=map_id,
            x=x,
            y=y,
            grh_index=511,
        )

        logger.info("Jugador %d dropeó %d oro al morir", user_id, gold_to_drop)

    async def _drop_random_items(
        self,
        user_id: int,
        map_id: int,
        x: int,
        y: int,
    ) -> None:
        """Dropea items aleatorios del inventario del jugador muerto.

        Args:
            user_id: ID del jugador.
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.
        """
        if not self.inventory_repo or not self.item_catalog:
            return

        # Obtener inventario
        inventory = await self.inventory_repo.get_inventory_slots(user_id)
        if not inventory:
            return

        # Seleccionar slots aleatorios para dropear (máximo MAX_ITEMS_TO_DROP)
        occupied_slots = list(inventory.keys())
        if not occupied_slots:
            return

        items_to_drop = min(len(occupied_slots), MAX_ITEMS_TO_DROP)
        slots_to_drop = random.sample(occupied_slots, items_to_drop)

        for slot in slots_to_drop:
            slot_data = inventory.get(slot)
            if not slot_data:
                continue

            item_id = slot_data.item_id
            quantity = slot_data.quantity

            # Obtener GrhIndex del catálogo
            grh_index = self.item_catalog.get_grh_index(item_id)
            if grh_index is None:
                continue

            # Vaciar el slot del inventario
            await self.inventory_repo.clear_slot(user_id, slot)

            # Crear ground item
            item: dict[str, int | str | None] = {
                "item_id": item_id,
                "quantity": quantity,
                "grh_index": grh_index,
                "owner_id": None,
                "spawn_time": None,
            }

            # Agregar al mapa
            self.map_manager.add_ground_item(map_id=map_id, x=x, y=y, item=item)

            # Broadcast
            await self.broadcast_service.broadcast_object_create(
                map_id=map_id,
                x=x,
                y=y,
                grh_index=grh_index,
            )

            item_name = self.item_catalog.get_item_name(item_id) or f"Item #{item_id}"
            logger.info(
                "Jugador %d dropeó %s (x%d) al morir",
                user_id,
                item_name,
                quantity,
            )

    async def _convert_to_ghost(
        self,
        user_id: int,
    ) -> None:
        """Convierte al jugador en fantasma (cambia su apariencia).

        Usa el sistema de morph existente para cambiar temporalmente
        la apariencia del jugador a fantasma.

        Args:
            user_id: ID del jugador.
        """
        # Usar fantasma masculino por defecto
        # En una implementación completa, se detectaría el género del personaje
        ghost_body = GHOST_BODY_MALE

        # Usar sistema de morph para cambiar apariencia a fantasma
        # Morph indefinido (un año en el futuro)
        morph_until = time.time() + (365 * 24 * 60 * 60)
        await self.player_repo.set_morphed_appearance(
            user_id,
            morphed_body=ghost_body,
            morphed_head=GHOST_HEAD,
            morphed_until=morph_until,
        )

        # Broadcast cambio de apariencia a todos los jugadores
        # Usamos remove + create para refrescar el personaje
        position = await self.player_repo.get_position(user_id)
        if position:
            # Remover y recrear el personaje para actualizar la vista
            await self.broadcast_service.broadcast_character_remove(
                map_id=position["map"],
                char_index=user_id,
            )

            # Obtener nombre del jugador para recrear
            player_name = await self._get_player_name(user_id)

            await self.broadcast_service.broadcast_character_create(
                map_id=position["map"],
                char_index=user_id,
                body=ghost_body,
                head=GHOST_HEAD,
                heading=position.get("heading", 3),
                x=position["x"],
                y=position["y"],
                name=player_name,
            )

        # Actualizar HP a 0 para indicar que está muerto
        await self.player_repo.update_hp(user_id, 0)

        logger.info("Jugador %d convertido en fantasma (body=%d)", user_id, ghost_body)

    async def _get_player_name(self, user_id: int) -> str:
        """Obtiene el nombre del jugador.

        Args:
            user_id: ID del jugador.

        Returns:
            Nombre del jugador o valor por defecto.
        """
        if self.account_repo:
            account_data = await self.account_repo.get_account_by_user_id(user_id)
            if account_data:
                return account_data.get("username", f"Player{user_id}")
        return f"Player{user_id}"

    async def _teleport_to_spawn(
        self,
        user_id: int,
    ) -> None:
        """Teletransporta al jugador al punto de respawn.

        Args:
            user_id: ID del jugador.
        """
        # Obtener posición actual
        old_position = await self.player_repo.get_position(user_id)
        old_map = old_position["map"] if old_position else 0

        # Actualizar posición a spawn
        await self.player_repo.set_position(
            user_id,
            x=DEFAULT_RESPAWN_X,
            y=DEFAULT_RESPAWN_Y,
            map_number=DEFAULT_RESPAWN_MAP,
            heading=3,  # Mirando al sur
        )

        # Si cambió de mapa, hacer el proceso de cambio de mapa
        if old_map != DEFAULT_RESPAWN_MAP:
            # Remover del mapa anterior
            self.map_manager.remove_player(old_map, user_id)

            # Nota: add_player requiere message_sender, pero no lo tenemos aquí
            # El jugador será agregado al nuevo mapa cuando envíe su primer packet

        logger.info(
            "Jugador %d teletransportado a spawn (%d, %d, %d)",
            user_id,
            DEFAULT_RESPAWN_MAP,
            DEFAULT_RESPAWN_X,
            DEFAULT_RESPAWN_Y,
        )
