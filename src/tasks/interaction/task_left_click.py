"""Tarea para click izquierdo en personajes/NPCs."""

import logging
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from src.models.items_catalog import ITEMS_CATALOG
from src.network.packet_data import LeftClickData
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.network.session_manager import SessionManager
from src.tasks.task import Task
from src.utils.packet_length_validator import PacketLengthValidator
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.game.map_manager import MapManager
    from src.messaging.message_sender import MessageSender
    from src.models.npc import NPC
    from src.repositories.bank_repository import BankRepository
    from src.repositories.door_repository import DoorRepository
    from src.repositories.merchant_repository import MerchantRepository
    from src.repositories.player_repository import PlayerRepository
    from src.services.map.door_service import DoorService
    from src.services.map.map_resources_service import MapResourcesService
    from src.utils.redis_client import RedisClient

logger = logging.getLogger(__name__)

# Constantes para GrhIndex de puertas de madera
WOODEN_DOOR_OPEN_GRH = 5592
WOODEN_DOOR_CLOSED_GRH = 5593
WOODEN_DOOR_OPEN_ID = 7
WOODEN_DOOR_CLOSED_ID = 8

# Cargar catálogo de carteles
_SIGNS_CATALOG: dict[int, dict[str, str]] = {}


def _load_signs_catalog() -> dict[int, dict[str, str]]:
    """Carga el catálogo de carteles desde signs.toml.

    Returns:
        Diccionario con GrhIndex como key y datos del cartel como value.
    """
    signs_path = Path(__file__).parent.parent.parent.parent / "data/items/world_objects/signs.toml"

    print(f"[SIGNS] Intentando cargar signs.toml desde: {signs_path}")
    print(f"[SIGNS] Archivo existe: {signs_path.exists()}")
    print(f"[SIGNS] Path absoluto: {signs_path.absolute()}")

    if not signs_path.exists():
        print("[SIGNS] ERROR: No se encontró signs.toml")
        logger.error("No se encontró signs.toml en %s", signs_path)
        return {}

    try:
        with Path(signs_path).open("rb") as f:
            data = tomllib.load(f)
            catalog: dict[int, dict[str, str]] = {}
            items = data.get("item", [])
            print(f"[SIGNS] Items encontrados en signs.toml: {len(items)}")

            for item in items:
                grh_index = item.get("GrhIndex")
                if grh_index and (grh_index not in catalog or not catalog[grh_index]["text"]):
                    catalog[grh_index] = {
                        "name": item.get("Name", "Cartel"),
                        "text": item.get("Texto", ""),
                    }

            logger.info("Catálogo de carteles cargado: %d GrhIndex únicos", len(catalog))
            return catalog
    except Exception as e:
        print(f"[SIGNS] ERROR cargando catálogo: {e}")
        logger.exception("Error cargando catálogo de carteles")
        return {}


# Cargar catálogo al importar el módulo
_SIGNS_CATALOG = _load_signs_catalog()


class TaskLeftClick(Task):
    """Maneja click izquierdo en personajes/NPCs."""

    def __init__(
        self,
        data: bytes,
        message_sender: MessageSender,
        player_repo: PlayerRepository,
        session_manager: SessionManager,  # noqa: ARG002
        map_manager: MapManager | None = None,
        map_resources: MapResourcesService | None = None,
        bank_repo: BankRepository | None = None,
        merchant_repo: MerchantRepository | None = None,
        door_service: DoorService | None = None,
        door_repo: DoorRepository | None = None,
        redis_client: RedisClient | None = None,
        session_data: dict[str, dict[str, int]] | None = None,
    ) -> None:
        """Inicializa la tarea de click izquierdo.

        Args:
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            player_repo: Repositorio de jugadores.
            session_manager: Gestor de sesiones.
            map_manager: Gestor de mapas para obtener NPCs.
            map_resources: Servicio de recursos del mapa.
            bank_repo: Repositorio de banco.
            merchant_repo: Repositorio de mercaderes.
            door_service: Servicio de puertas.
            door_repo: Repositorio de puertas.
            redis_client: Cliente Redis.
            session_data: Datos de sesión.
        """
        super().__init__(data, message_sender)
        self.player_repo = player_repo
        self.map_manager = map_manager
        self.map_resources = map_resources
        self.bank_repo = bank_repo
        self.merchant_repo = merchant_repo
        self.door_service = door_service
        self.door_repo = door_repo
        self.redis_client = redis_client
        self.session_data = session_data or {}

    async def execute(self) -> None:
        """Ejecuta click izquierdo en personaje/NPC."""
        # Validar longitud del packet usando PacketLengthValidator
        if not await PacketLengthValidator.validate_min_length(self.data, 26, self.message_sender):
            return

        # Verificar que el jugador esté logueado
        user_id = SessionManager.get_user_id(self.session_data)
        if user_id is None:
            logger.warning("Intento de click sin estar logueado")
            return

        if not self.map_manager or not self.player_repo:
            logger.error("Dependencias no disponibles para click en NPC")
            return

        # Parsear y validar packet
        reader = PacketReader(self.data)
        validator = PacketValidator(reader)

        # Usar nueva API consistente
        coords_result = validator.validate_coordinates(max_x=100, max_y=100)

        if not coords_result.success:
            await self.message_sender.send_console_msg(
                coords_result.error_message or "Coordenadas inválidas"
            )
            return

        # Crear dataclass con datos validados
        if coords_result.data is None:
            await self.message_sender.send_console_msg("Coordenadas inválidas")
            return
        x, y = coords_result.data
        click_data = LeftClickData(x=x, y=y)

        logger.info(
            "user_id %d hizo click en posición (%d, %d)", user_id, click_data.x, click_data.y
        )

        try:
            # Obtener posición del jugador para saber en qué mapa está
            position = await self.player_repo.get_position(user_id)
            if not position:
                logger.warning("No se pudo obtener posición del jugador %d", user_id)
                return

            map_id = position["map"]

            # Buscar NPC en esa posición
            all_npcs = self.map_manager.get_npcs_in_map(map_id)
            npc_found = None
            for npc in all_npcs:
                if npc.x == click_data.x and npc.y == click_data.y:
                    npc_found = npc
                    break

            if npc_found:
                await self._handle_npc_click(user_id, npc_found)
            else:
                # No hay NPC, mostrar información del tile
                await self._show_tile_info(map_id, click_data.x, click_data.y)

        except Exception:
            logger.exception("Error al parsear packet LEFT_CLICK")

    async def _handle_npc_click(self, user_id: int, npc: NPC) -> None:
        """Maneja click en un NPC.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC.
        """
        # Si es un mercader, abrir ventana de comercio
        if npc.is_merchant:
            await self._open_merchant_window(user_id, npc)
            return

        # Si es un banquero, abrir ventana de banco
        if npc.is_banker:
            await self._open_bank_window(user_id, npc)
            return

        # Mostrar información básica del NPC (solo ASCII para evitar crashes)
        info_parts = [f"[{npc.name}]"]

        if npc.description:
            info_parts.append(npc.description)

        if npc.is_hostile:
            info_parts.append(f"Nivel {npc.level} - Hostil")
        else:
            info_parts.append(f"Nivel {npc.level} - Amigable")

        info_parts.append(f"HP: {npc.hp}/{npc.max_hp}")

        info_message = " | ".join(info_parts)
        await self.message_sender.send_console_msg(info_message)

        logger.info(
            "user_id %d obtuvo información de NPC %s (CharIndex: %d)",
            user_id,
            npc.name,
            npc.char_index,
        )

    async def _open_merchant_window(self, user_id: int, npc: NPC) -> None:
        """Abre la ventana de comercio con un mercader.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC mercader.
        """
        if not self.merchant_repo or not self.redis_client:
            logger.error("Dependencias no disponibles para abrir comercio")
            await self.message_sender.send_console_msg("Error al abrir comercio")
            return

        logger.info(
            "user_id %d abriendo comercio con %s (npc_id=%d)", user_id, npc.name, npc.npc_id
        )

        # Guardar mercader activo en sesión de Redis
        key = RedisKeys.session_active_merchant(user_id)
        await self.redis_client.redis.set(key, str(npc.npc_id))

        # Enviar packet COMMERCE_INIT vacío PRIMERO (abre la ventana)
        await self.message_sender.send_commerce_init_empty()

        # Obtener inventario del mercader
        merchant_items = await self.merchant_repo.get_all_items(npc.npc_id)

        if not merchant_items:
            await self.message_sender.send_console_msg(f"{npc.name} no tiene nada para vender.")
            logger.warning("Mercader %d no tiene inventario", npc.npc_id)
            return

        # Preparar lista de items para el packet COMMERCE_INIT
        # Formato: (slot, item_id, name, quantity, price, grh_index, obj_type,
        #           max_hit, min_hit, max_def, min_def)
        items_data = []
        for merchant_item in merchant_items:
            item = ITEMS_CATALOG.get(merchant_item.item_id)
            if not item:
                logger.warning("Item %d no encontrado en catálogo", merchant_item.item_id)
                continue

            items_data.append(
                (
                    merchant_item.slot,
                    merchant_item.item_id,
                    item.name,
                    merchant_item.quantity,
                    item.value,  # Precio de compra
                    item.graphic_id,
                    item.item_type.to_client_type(),  # Convertir enum a número del protocolo
                    item.max_damage or 0,
                    item.min_damage or 0,
                    item.defense or 0,
                    item.defense or 0,
                )
            )

        # Enviar items del mercader usando ChangeNPCInventorySlot
        for item_data in items_data:
            (
                slot,
                item_id,
                name,
                quantity,
                price,
                grh_index,
                obj_type,
                max_hit,
                min_hit,
                max_def,
                min_def,
            ) = item_data
            await self.message_sender.send_change_npc_inventory_slot(
                slot=slot,
                name=name,
                amount=quantity,
                sale_price=float(price),
                grh_id=grh_index,
                item_id=item_id,
                item_type=obj_type,
                max_hit=max_hit,
                min_hit=min_hit,
                max_def=max_def,
                min_def=min_def,
            )

        logger.info(
            "Ventana de comercio abierta para user_id %d con mercader %s (%d items)",
            user_id,
            npc.name,
            len(items_data),
        )

    async def _open_bank_window(self, user_id: int, npc: NPC) -> None:
        """Abre la ventana de banco para el jugador.

        Args:
            user_id: ID del usuario.
            npc: Instancia del NPC banquero.
        """
        if not self.bank_repo:
            logger.error("BankRepository no disponible")
            await self.message_sender.send_console_msg("El banco no está disponible")
            return

        logger.info("user_id %d abriendo banco con %s (npc_id=%d)", user_id, npc.name, npc.npc_id)

        # Enviar packet BANK_INIT vacío PRIMERO (abre la ventana)
        await self.message_sender.send_bank_init_empty()

        # Obtener todos los items del banco
        bank_items = await self.bank_repo.get_all_items(user_id)

        # Enviar items del banco usando ChangeBankSlot
        for bank_item in bank_items:
            item = ITEMS_CATALOG.get(bank_item.item_id)
            if not item:
                logger.warning("Item %d no encontrado en catálogo", bank_item.item_id)
                continue

            await self.message_sender.send_change_bank_slot(
                slot=bank_item.slot,
                item_id=bank_item.item_id,
                name=item.name,
                amount=bank_item.quantity,
                grh_id=item.graphic_id,
                item_type=item.item_type.to_client_type(),
                max_hit=item.max_damage or 0,
                min_hit=item.min_damage or 0,
                max_def=item.defense or 0,
                min_def=item.defense or 0,
            )

        # Enviar oro del banco
        bank_gold = await self.bank_repo.get_gold(user_id)
        await self.message_sender.send_update_bank_gold(bank_gold)

        logger.info(
            "Ventana de banco abierta para user_id %d con banquero %s (%d items, %d oro)",
            user_id,
            npc.name,
            len(bank_items),
            bank_gold,
        )

    async def _show_tile_info(self, map_id: int, x: int, y: int) -> None:
        """Muestra información detallada de un tile.

        Args:
            map_id: ID del mapa.
            x: Coordenada X del tile.
            y: Coordenada Y del tile.
        """
        # Verificar si hay una puerta en esta posición
        door_handled = await self._handle_door_click(map_id, x, y)
        if door_handled:
            return

        # Verificar si hay un cartel en esta posición
        sign_text = await self._get_sign_text(map_id, x, y)
        if sign_text:
            # Hay un cartel, mostrar su texto
            await self.message_sender.send_console_msg(sign_text)
            return

        # No hay cartel, mostrar información del tile
        max_items_to_show = 5
        info_lines = [f"=== Tile ({x}, {y}) - Mapa {map_id} ==="]

        # Verificar recursos del mapa
        resources = []
        if self.map_resources:
            is_blocked = self.map_resources.is_blocked(map_id, x, y)
            has_water = self.map_resources.has_water(map_id, x, y)
            has_tree = self.map_resources.has_tree(map_id, x, y)
            has_mine = self.map_resources.has_mine(map_id, x, y)

            logger.info(
                "TILE_RESOURCES map=%d (%d,%d): blocked=%s water=%s tree=%s mine=%s",
                map_id,
                x,
                y,
                is_blocked,
                has_water,
                has_tree,
                has_mine,
            )

            if is_blocked:
                info_lines.append("Estado: Bloqueado")

            if has_water:
                resources.append("Agua")
            if has_tree:
                resources.append("Arbol")
            if has_mine:
                resources.append("Yacimiento")

        if resources:
            info_lines.append(f"Recursos: {', '.join(resources)}")

        # Verificar objetos en el suelo
        if self.map_manager:
            ground_items = self.map_manager.get_ground_items(map_id, x, y)
            if ground_items:
                items_str = []
                for item_data in ground_items[:max_items_to_show]:
                    item_id = item_data.get("item_id")
                    quantity = item_data.get("quantity", 1)
                    item = (
                        ITEMS_CATALOG.get(int(item_id))
                        if item_id and isinstance(item_id, int)
                        else None
                    )
                    if item:
                        items_str.append(f"{item.name} x{quantity}")

                if items_str:
                    info_lines.append(f"Items en el suelo: {', '.join(items_str)}")
                    if len(ground_items) > max_items_to_show:
                        info_lines.append(f"... y {len(ground_items) - max_items_to_show} mas")

        # Si no hay nada interesante
        if len(info_lines) == 1:
            info_lines.append("Tile vacio")

        # Enviar mensaje
        message = " | ".join(info_lines)
        await self.message_sender.send_console_msg(message)

    async def _get_sign_text(self, map_id: int, x: int, y: int) -> str | None:
        """Obtiene el texto de un cartel si existe en la posición.

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            Texto del cartel o None si no hay cartel.
        """
        if not self.map_resources:
            return None

        # Buscar cartel en la posición
        sign_grh = self.map_resources.get_sign_at(map_id, x, y)
        if not sign_grh:
            return None

        # Buscar en el catálogo
        sign_data = _SIGNS_CATALOG.get(sign_grh)
        if not sign_data:
            logger.warning("Cartel con GrhIndex=%d no encontrado en catálogo", sign_grh)
            return "[Cartel sin texto]"

        return sign_data["text"]

    async def _handle_door_click(self, map_id: int, x: int, y: int) -> bool:  # noqa: PLR0915
        """Maneja el click en una puerta (abrir/cerrar).

        Args:
            map_id: ID del mapa.
            x: Coordenada X.
            y: Coordenada Y.

        Returns:
            True si se manejó una puerta, False si no hay puerta.
        """
        if not self.map_resources or not self.door_service or not self.door_repo:
            return False

        # MÉTODO ALTERNATIVO: Buscar puerta por GrhIndex en MapResourcesService
        # (Las puertas no están en los archivos de mapa VB6)
        # Buscar puerta en la posición
        door_grh = self.map_resources.get_door_at(map_id, x, y)

        # Si no hay puerta en MapResourcesService, no es una puerta
        if not door_grh:
            return False

        # Verificar si hay un estado guardado en Redis
        saved_state = await self.door_repo.get_door_state(map_id, x, y)

        if saved_state:
            # Usar el estado guardado (item_id, is_open)
            current_item_id, _current_is_open = saved_state
            door_info = self.door_service.get_door_by_id(current_item_id)
        else:
            # IMPORTANTE: No usar get_door_by_grh() porque puede haber múltiples puertas
            # con el mismo GrhIndex. En su lugar, usar el item_id inicial de map_doors.toml
            # Por ahora, buscar por GrhIndex pero esto debería mejorarse
            door_info = self.door_service.get_door_by_grh(door_grh)

            # Si encontramos una puerta, usar su item_id inicial correcto
            # Para puertas de madera, forzar los IDs correctos
            if door_info and door_grh == WOODEN_DOOR_CLOSED_GRH:
                # Forzar item_id para puerta cerrada
                door_info = self.door_service.get_door_by_id(WOODEN_DOOR_CLOSED_ID)
            elif door_info and door_grh == WOODEN_DOOR_OPEN_GRH:
                # Forzar item_id para puerta abierta
                door_info = self.door_service.get_door_by_id(WOODEN_DOOR_OPEN_ID)

        if not door_info:
            logger.warning("Puerta con GrhIndex=%d no encontrada en catálogo", door_grh)
            await self.message_sender.send_console_msg("No puedes interactuar con esto.")
            return True

        logger.info(
            "Puerta detectada: item_id=%d, name=%s, is_open=%s, requires_key=%s, key_id=%s",
            door_info.item_id,
            door_info.name,
            door_info.is_open,
            door_info.requires_key,
            door_info.key_id,
        )

        # Verificar si la puerta requiere llave
        if door_info.requires_key:
            await self.message_sender.send_console_msg("La puerta está cerrada con llave.")
            return True

        # Alternar estado de la puerta
        new_item_id, new_is_open = self.door_service.toggle_door(door_info)

        # Guardar nuevo estado en Redis
        await self.door_repo.set_door_state(map_id, x, y, new_item_id, new_is_open)

        # Obtener información de la nueva puerta
        new_door_info = self.door_service.get_door_by_id(new_item_id)
        if not new_door_info:
            logger.error("No se encontró información para puerta ID=%d", new_item_id)
            return True

        # Actualizar bloqueo del tile en MapManager
        # Las puertas ocupan 2 tiles adyacentes
        if self.map_manager:
            # Determinar ambos tiles de la puerta (x y x+1, o x-1 y x)
            # Intentamos ambos tiles adyacentes
            tiles_to_update = [(x, y)]

            # Verificar si hay puerta en x-1 o x+1
            if not self.map_resources or not self.door_service or not self.door_repo:
                return False

            door_left = self.map_resources.get_door_at(map_id, x - 1, y)
            door_right = self.map_resources.get_door_at(map_id, x + 1, y)

            if door_left:
                tiles_to_update.append((x - 1, y))
                logger.debug("Puerta adyacente encontrada en (%d, %d)", x - 1, y)
            if door_right:
                tiles_to_update.append((x + 1, y))
                logger.debug("Puerta adyacente encontrada en (%d, %d)", x + 1, y)

            logger.info(
                "Actualizando %d tiles de puerta: %s", len(tiles_to_update), tiles_to_update
            )

            # Actualizar bloqueo de todos los tiles
            for tile_x, tile_y in tiles_to_update:
                if new_is_open:
                    self.map_manager.unblock_tile(map_id, tile_x, tile_y)
                    # Puerta abierta: eliminar objeto y desbloquear tile
                    await self.message_sender.send_object_delete(tile_x, tile_y)
                    await self.message_sender.send_block_position(tile_x, tile_y, blocked=False)
                    logger.debug(
                        "Tile (%d, %d) - Puerta abierta: OBJECT_DELETE + BLOCK_POSITION(false)",
                        tile_x,
                        tile_y,
                    )
                else:
                    self.map_manager.block_tile(map_id, tile_x, tile_y)
                    # Puerta cerrada: crear objeto y bloquear tile
                    await self.message_sender.send_object_create(
                        tile_x, tile_y, new_door_info.grh_index
                    )
                    await self.message_sender.send_block_position(tile_x, tile_y, blocked=True)
                    logger.debug(
                        "Tile (%d, %d) - Puerta cerrada: OBJECT_CREATE + BLOCK_POSITION(true)",
                        tile_x,
                        tile_y,
                    )

                # Guardar estado en Redis para cada tile
                await self.door_repo.set_door_state(
                    map_id, tile_x, tile_y, new_item_id, new_is_open
                )

        action = "abierta" if new_is_open else "cerrada"
        await self.message_sender.send_console_msg(f"Puerta {action}.")

        logger.info(
            "Puerta en (%d, %d, %d) %s: %s -> %s (GrhIndex: %d -> %d)",
            map_id,
            x,
            y,
            action,
            door_info.name,
            new_door_info.name,
            door_info.grh_index,
            new_door_info.grh_index,
        )

        return True
