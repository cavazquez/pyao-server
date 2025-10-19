"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys
import time
from typing import TYPE_CHECKING

import redis
from src.account_repository import AccountRepository
from src.bank_repository import BankRepository
from src.client_connection import ClientConnection
from src.combat_service import CombatService
from src.commerce_service import CommerceService
from src.effect_gold_decay import GoldDecayEffect
from src.effect_hunger_thirst import HungerThirstEffect
from src.effect_npc_movement import NPCMovementEffect
from src.equipment_repository import EquipmentRepository
from src.game_tick import GameTick
from src.ground_items_repository import GroundItemsRepository
from src.inventory_repository import InventoryRepository
from src.item_catalog import ItemCatalog
from src.items_catalog import ITEMS_CATALOG
from src.loot_table_service import LootTableService
from src.map_manager import MapManager
from src.meditation_effect import MeditationEffect
from src.merchant_repository import MerchantRepository
from src.message_sender import MessageSender
from src.multiplayer_broadcast_service import MultiplayerBroadcastService
from src.npc_ai_effect import NPCAIEffect
from src.npc_ai_service import NPCAIService
from src.npc_catalog import NPCCatalog
from src.npc_repository import NPCRepository
from src.npc_respawn_service import NPCRespawnService
from src.npc_service import NPCService
from src.packet_handlers import TASK_HANDLERS
from src.player_repository import PlayerRepository
from src.redis_client import RedisClient
from src.redis_config import RedisKeys
from src.server_repository import ServerRepository
from src.spell_catalog import SpellCatalog
from src.spell_service import SpellService
from src.spellbook_repository import SpellbookRepository
from src.task_account import TaskCreateAccount
from src.task_attack import TaskAttack
from src.task_attributes import TaskRequestAttributes
from src.task_bank_deposit import TaskBankDeposit
from src.task_bank_end import TaskBankEnd
from src.task_bank_extract import TaskBankExtract
from src.task_cast_spell import TaskCastSpell
from src.task_change_heading import TaskChangeHeading
from src.task_commerce_buy import TaskCommerceBuy
from src.task_commerce_end import TaskCommerceEnd
from src.task_commerce_sell import TaskCommerceSell
from src.task_dice import TaskDice
from src.task_double_click import TaskDoubleClick
from src.task_drop import TaskDrop
from src.task_equip_item import TaskEquipItem
from src.task_information import TaskInformation
from src.task_inventory_click import TaskInventoryClick
from src.task_left_click import TaskLeftClick
from src.task_login import TaskLogin
from src.task_meditate import TaskMeditate
from src.task_motd import TaskMotd
from src.task_null import TaskNull
from src.task_online import TaskOnline
from src.task_pickup import TaskPickup
from src.task_quit import TaskQuit
from src.task_request_position_update import TaskRequestPositionUpdate
from src.task_request_stats import TaskRequestStats
from src.task_talk import TaskTalk
from src.task_uptime import TaskUptime
from src.task_walk import TaskWalk

if TYPE_CHECKING:
    from src.task import Task

logger = logging.getLogger(__name__)


class ArgentumServer:
    """Servidor TCP para Argentum Online."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 7666,
    ) -> None:
        """Inicializa el servidor.

        Args:
            host: Dirección IP donde escuchar (se sobrescribe con Redis).
            port: Puerto donde escuchar (se sobrescribe con Redis).
        """
        # TODO: Los objetos deberían crearse lo más completos posibles y funcionales.
        # Analizar si se puede cambiar el orden y reducir la cantidad de None.
        # Ver TODO_ARQUITECTURA.md sección 3 para propuestas de solución.
        # Considerar usar Builder Pattern o Factory para inicialización completa.
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.redis_client: RedisClient | None = None
        self.player_repo: PlayerRepository | None = None
        self.account_repo: AccountRepository | None = None
        self.server_repo: ServerRepository | None = None
        self.ground_items_repo: GroundItemsRepository | None = None
        self.map_manager: MapManager | None = None  # Gestor de jugadores y NPCs por mapa
        self.game_tick: GameTick | None = None  # Sistema de tick genérico del juego
        self.npc_service: NPCService | None = None  # Servicio de NPCs
        self.npc_respawn_service: NPCRespawnService | None = None  # Servicio de respawn de NPCs
        self.item_catalog: ItemCatalog | None = None  # Catálogo de items
        self.loot_table_service: LootTableService | None = None  # Servicio de loot tables
        self.spell_catalog: SpellCatalog | None = None  # Catálogo de hechizos
        self.spell_service: SpellService | None = None  # Servicio de hechizos
        self.spellbook_repo: SpellbookRepository | None = None  # Repositorio de libro de hechizos
        self.equipment_repo: EquipmentRepository | None = None  # Repositorio de equipamiento
        self.broadcast_service: MultiplayerBroadcastService | None = None  # Servicio de broadcast
        self.merchant_repo: MerchantRepository | None = None  # Repositorio de mercaderes
        self.bank_repo: BankRepository | None = None  # Repositorio de banco
        self.commerce_service: CommerceService | None = None  # Servicio de comercio

    # TODO: Revisar la separación de capas y responsabilidades.
    # Este método tiene demasiada lógica de creación de tasks con dependencias.
    # Ver TODO_ARQUITECTURA.md sección 2 para propuestas de mejora.
    # Considerar: Service Container, Dependency Injection, o Factory Pattern.
    def create_task(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]],
    ) -> Task:
        """Crea la tarea apropiada según el PacketID recibido.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            session_data: Datos de sesión (mutable, compartido entre tareas).

        Returns:
            Instancia de la tarea correspondiente.
        """
        if len(data) == 0:
            return TaskNull(data, message_sender)

        packet_id = data[0]

        # Buscar handler en el diccionario
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)

        # Pasar parámetros adicionales según el tipo de tarea
        if task_class is TaskLogin:
            return TaskLogin(
                data,
                message_sender,
                self.player_repo,
                self.account_repo,
                self.map_manager,
                session_data,
                self.npc_service,
                self.server_repo,
                self.spellbook_repo,
                self.spell_catalog,
                self.equipment_repo,
            )
        if task_class is TaskCreateAccount:
            return TaskCreateAccount(
                data,
                message_sender,
                self.player_repo,
                self.account_repo,
                self.map_manager,
                session_data,
                self.npc_service,
                self.server_repo,
                self.spellbook_repo,
                self.spell_catalog,
                self.equipment_repo,
            )
        if task_class is TaskDice:
            return TaskDice(data, message_sender, session_data, self.server_repo)
        if task_class is TaskRequestAttributes:
            return TaskRequestAttributes(data, message_sender, self.player_repo, session_data)
        if task_class is TaskTalk:
            return TaskTalk(
                data,
                message_sender,
                self.player_repo,
                self.account_repo,
                self.map_manager,
                session_data,
            )
        if task_class is TaskWalk:
            return TaskWalk(
                data,
                message_sender,
                self.player_repo,
                self.map_manager,
                self.broadcast_service,
                session_data,
            )
        if task_class is TaskChangeHeading:
            return TaskChangeHeading(
                data,
                message_sender,
                self.player_repo,
                self.account_repo,
                self.map_manager,
                session_data,
            )
        if task_class is TaskRequestStats:
            return TaskRequestStats(data, message_sender, self.player_repo, session_data)
        if task_class is TaskRequestPositionUpdate:
            return TaskRequestPositionUpdate(data, message_sender, self.player_repo, session_data)
        if task_class is TaskOnline:
            return TaskOnline(data, message_sender, self.map_manager, session_data)
        if task_class is TaskMotd:
            return TaskMotd(data, message_sender, self.server_repo)
        if task_class is TaskInformation:
            return TaskInformation(data, message_sender, self.server_repo, self.map_manager)
        if task_class is TaskUptime:
            return TaskUptime(data, message_sender, self.server_repo)
        if task_class is TaskQuit:
            return TaskQuit(data, message_sender, self.player_repo, self.map_manager, session_data)
        if task_class is TaskDoubleClick:
            return TaskDoubleClick(
                data, message_sender, self.player_repo, self.map_manager, session_data
            )
        if task_class is TaskLeftClick:
            return TaskLeftClick(
                data,
                message_sender,
                self.player_repo,
                self.map_manager,
                self.merchant_repo,
                self.bank_repo,
                self.redis_client,
                session_data,
            )
        if task_class is TaskCastSpell:
            return TaskCastSpell(
                data,
                message_sender,
                self.player_repo,
                self.spell_service,
                session_data,
                self.spellbook_repo,
            )
        if task_class is TaskMeditate:
            return TaskMeditate(data, message_sender, self.player_repo, session_data)
        if task_class is TaskInventoryClick:
            return TaskInventoryClick(
                data, message_sender, self.player_repo, session_data, self.equipment_repo
            )
        if task_class is TaskEquipItem:
            return TaskEquipItem(
                data, message_sender, self.player_repo, session_data, self.equipment_repo
            )
        if task_class is TaskAttack:
            return TaskAttack(
                data,
                message_sender,
                self.player_repo,
                self.combat_service,
                self.map_manager,
                self.npc_service,
                self.broadcast_service,
                self.npc_respawn_service,
                self.loot_table_service,
                self.item_catalog,
                session_data,
            )
        if task_class is TaskPickup:
            return TaskPickup(
                data,
                message_sender,
                self.player_repo,
                self.inventory_repo,
                self.map_manager,
                self.broadcast_service,
                self.item_catalog,
                session_data,
            )
        if task_class is TaskDrop:
            return TaskDrop(
                data,
                message_sender,
                self.player_repo,
                self.inventory_repo,
                self.map_manager,
                self.broadcast_service,
                session_data,
            )
        if task_class is TaskCommerceBuy:
            return TaskCommerceBuy(
                data,
                message_sender,
                self.commerce_service,
                self.player_repo,
                self.inventory_repo,
                self.redis_client,
                session_data,
            )
        if task_class is TaskCommerceSell:
            return TaskCommerceSell(
                data,
                message_sender,
                self.commerce_service,
                self.player_repo,
                self.inventory_repo,
                self.redis_client,
                session_data,
            )
        if task_class is TaskBankDeposit:
            return TaskBankDeposit(
                data,
                message_sender,
                self.bank_repo,
                self.inventory_repo,
                self.player_repo,
                session_data,
            )
        if task_class is TaskBankExtract:
            return TaskBankExtract(
                data,
                message_sender,
                self.bank_repo,
                self.inventory_repo,
                self.player_repo,
                session_data,
            )
        if task_class is TaskBankEnd:
            return TaskBankEnd(data, message_sender, session_data)
        if task_class is TaskCommerceEnd:
            return TaskCommerceEnd(data, message_sender)

        return task_class(data, message_sender)

    async def handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Maneja la conexión de un cliente.

        Args:
            reader: Stream para leer datos del cliente (pasado a ClientConnection).
            writer: Stream para escribir datos al cliente (pasado a ClientConnection).
        """
        connection = ClientConnection(reader, writer)
        message_sender = MessageSender(connection)
        logger.info("Nueva conexión desde %s", connection.address)

        # Incrementar contador de conexiones en Redis
        if self.redis_client:
            await self.redis_client.increment_connections()
            connections = await self.redis_client.get_connections_count()
            logger.info("Conexiones activas: %d", connections)

        # Datos de sesión compartidos entre tareas (mutable)
        session_data: dict[str, dict[str, int]] = {}

        try:
            while True:
                data = await connection.receive()
                if not data:
                    break

                # Crear y ejecutar tarea apropiada según el mensaje
                task = self.create_task(data, message_sender, session_data)
                await task.execute()

        except Exception:
            logger.exception("Error manejando cliente %s", connection.address)
        finally:
            logger.info("Cerrando conexión con %s", connection.address)

            # Broadcast multijugador: notificar desconexión
            if "user_id" in session_data and self.player_repo:
                user_id_value = session_data["user_id"]
                if not isinstance(user_id_value, dict):
                    user_id = int(user_id_value)

                    # Obtener el mapa del jugador antes de removerlo
                    position = await self.player_repo.get_position(user_id)
                    if position:
                        map_id = position["map"]

                        # Enviar CHARACTER_REMOVE a todos los jugadores en el mapa
                        other_senders = self.map_manager.get_all_message_senders_in_map(
                            map_id, exclude_user_id=user_id
                        )
                        for sender in other_senders:
                            await sender.send_character_remove(user_id)

                        logger.info(
                            "Desconexión de user %d notificada a %d jugadores en mapa %d",
                            user_id,
                            len(other_senders),
                            map_id,
                        )

                    # Remover jugador del MapManager
                    self.map_manager.remove_player_from_all_maps(user_id)

            connection.close()
            await connection.wait_closed()

            # Decrementar contador de conexiones en Redis
            if self.redis_client:
                await self.redis_client.decrement_connections()
                connections = await self.redis_client.get_connections_count()
                logger.info("Conexiones activas: %d", connections)

    async def _initialize_dice_config(self) -> None:
        """Inicializa la configuración de dados en Redis si no existe."""
        if not self.redis_client or not self.server_repo:
            return

        dice_min_key = "server:dice:min_value"
        dice_max_key = "server:dice:max_value"

        # Verificar si existen, si no, crear con valores por defecto
        if await self.redis_client.redis.get(dice_min_key) is None:
            await self.server_repo.set_dice_min_value(6)
            logger.info("Valor mínimo de dados inicializado: 6")

        if await self.redis_client.redis.get(dice_max_key) is None:
            await self.server_repo.set_dice_max_value(18)
            logger.info("Valor máximo de dados inicializado: 18")

        dice_min = await self.server_repo.get_dice_min_value()
        dice_max = await self.server_repo.get_dice_max_value()
        logger.info("Configuración de dados: min=%d, max=%d", dice_min, dice_max)

    async def _initialize_effects_config(self) -> None:
        """Inicializa la configuración de efectos en Redis si no existe."""
        if not self.redis_client:
            return

        # Hambre y Sed - 180 segundos (3 minutos)
        # SIEMPRE establecer valores correctos (sobrescribe valores de testing)
        await self.redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_SED, "180")
        logger.info("Intervalo de sed configurado: 180 segundos (3 minutos)")

        await self.redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_INTERVAL_HAMBRE, "180")
        logger.info("Intervalo de hambre configurado: 180 segundos (3 minutos)")

        if await self.redis_client.redis.get(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA) is None:
            await self.redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_AGUA, "10")
            logger.info("Reducción de agua inicializada: 10 puntos")

        if (
            await self.redis_client.redis.get(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE)
            is None
        ):
            await self.redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_REDUCCION_HAMBRE, "10")
            logger.info("Reducción de hambre inicializada: 10 puntos")

        if await self.redis_client.redis.get(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED) is None:
            await self.redis_client.redis.set(RedisKeys.CONFIG_HUNGER_THIRST_ENABLED, "1")
            logger.info("Sistema de hambre/sed habilitado por defecto")

    async def _load_ground_items(self) -> None:
        """Carga ground items desde Redis para mapas activos."""
        if not self.map_manager:
            return

        # Por ahora cargar solo mapa 1 (el mapa principal)
        # TODO: Cargar dinámicamente según mapas con jugadores/NPCs
        await self.map_manager.load_ground_items(1)

    async def start(self) -> None:  # noqa: PLR0915
        """Inicia el servidor TCP."""
        # Conectar a Redis (obligatorio)
        try:
            self.redis_client = RedisClient()
            await self.redis_client.connect()

            # Crear repositorios
            self.player_repo = PlayerRepository(self.redis_client)
            self.account_repo = AccountRepository(self.redis_client)
            self.server_repo = ServerRepository(self.redis_client)

            # Obtener configuración desde Redis
            self.host = await self.redis_client.get_server_host()
            self.port = await self.redis_client.get_server_port()
            logger.info("Configuración cargada desde Redis: %s:%d", self.host, self.port)

            # Resetear contador de conexiones
            await self.redis_client.redis.set("server:connections:count", "0")

            # Establecer timestamp de inicio del servidor
            await self.server_repo.set_uptime_start(int(time.time()))

            # Inicializar configuración de dados
            await self._initialize_dice_config()

            # Obtener MOTD desde Redis
            motd = await self.server_repo.get_motd()
            if motd == "Bienvenido a Argentum Online!\nServidor en desarrollo.":
                # Es el mensaje por defecto, establecer uno inicial
                initial_motd = (
                    "» Bienvenido a Argentum Online! «\n"
                    "• Servidor en desarrollo.\n"
                    "• Usa /AYUDA para ver los comandos disponibles.\n"
                    "¡Buena suerte en tu aventura!"
                )
                await self.server_repo.set_motd(initial_motd)
                logger.info("MOTD inicial establecido")

            # Inicializar sistema de ground items y MapManager (necesario para otros servicios)
            self.ground_items_repo = GroundItemsRepository(self.redis_client)
            self.map_manager = MapManager(self.ground_items_repo)
            logger.info("Sistema de ground items y MapManager inicializados")

            # Inicializar sistema de tick del juego
            self.game_tick = GameTick(
                player_repo=self.player_repo,
                map_manager=self.map_manager,
                tick_interval=0.5,  # 0.5 segundos por tick (cada efecto decide su intervalo)
            )

            # Agregar efectos al sistema de tick (configuración desde Redis)
            hunger_thirst_enabled = await self.server_repo.get_effect_config_bool(
                RedisKeys.CONFIG_HUNGER_THIRST_ENABLED, default=True
            )
            if hunger_thirst_enabled:
                self.game_tick.add_effect(HungerThirstEffect(self.server_repo))
                logger.info("Efecto de hambre/sed habilitado")

            gold_decay_enabled = await self.server_repo.get_effect_config_bool(
                RedisKeys.CONFIG_GOLD_DECAY_ENABLED, default=True
            )
            if gold_decay_enabled:
                self.game_tick.add_effect(GoldDecayEffect(self.server_repo))
                logger.info("Efecto de reducción de oro habilitado")

            # Agregar efecto de meditación (siempre habilitado)
            self.game_tick.add_effect(MeditationEffect(interval_seconds=3.0))
            logger.info("Efecto de meditación habilitado")

            # Inicializar servicio de broadcast multijugador
            self.broadcast_service = MultiplayerBroadcastService(
                self.map_manager, self.player_repo, self.account_repo
            )
            logger.info("Servicio de broadcast multijugador inicializado")

            # Inicializar sistema de NPCs
            npc_catalog = NPCCatalog()
            npc_repository = NPCRepository(self.redis_client)
            # map_manager ya está inicializado arriba
            self.npc_service = NPCService(
                npc_repository, npc_catalog, self.map_manager, self.broadcast_service
            )
            await self.npc_service.initialize_world_npcs()
            logger.info("Sistema de NPCs inicializado")

            # Inicializar servicio de respawn de NPCs
            self.npc_respawn_service = NPCRespawnService(self.npc_service)
            logger.info("Sistema de respawn de NPCs inicializado")

            # Inicializar catálogo de items y loot tables
            self.item_catalog = ItemCatalog()
            self.loot_table_service = LootTableService()
            logger.info("Sistema de items y loot tables inicializado")

            # Agregar efecto de movimiento de NPCs
            self.game_tick.add_effect(NPCMovementEffect(self.npc_service, interval_seconds=5.0))
            logger.info("Efecto de movimiento de NPCs habilitado")

            # Inicializar sistema de magia
            self.spell_catalog = SpellCatalog()
            # map_manager ya está inicializado arriba
            self.spell_service = SpellService(
                self.spell_catalog, self.player_repo, npc_repository, self.map_manager
            )
            self.spellbook_repo = SpellbookRepository(self.redis_client)
            logger.info("Sistema de magia inicializado")

            # Inicializar sistema de equipamiento
            self.equipment_repo = EquipmentRepository(self.redis_client)
            logger.info("Sistema de equipamiento inicializado")

            # Inicializar sistema de inventario
            self.inventory_repo = InventoryRepository(self.redis_client)
            logger.info("Sistema de inventario inicializado")

            # Inicializar sistema de mercaderes
            self.merchant_repo = MerchantRepository(self.redis_client)
            logger.info("Sistema de mercaderes inicializado")

            # Inicializar sistema de banco
            self.bank_repo = BankRepository(self.redis_client)
            logger.info("Sistema de banco inicializado")

            # Inicializar servicio de comercio
            self.commerce_service = CommerceService(
                self.inventory_repo,
                self.merchant_repo,
                ITEMS_CATALOG,
                self.player_repo,
            )
            logger.info("Servicio de comercio inicializado")

            # Inicializar sistema de combate
            self.combat_service = CombatService(
                self.player_repo,
                npc_repository,
                self.equipment_repo,
                self.inventory_repo,
            )
            logger.info("Sistema de combate inicializado")

            # Inicializar servicio de IA de NPCs (después de combat_service)
            self.npc_ai_service = NPCAIService(
                self.npc_service,
                self.map_manager,
                self.player_repo,
                self.combat_service,
                self.broadcast_service,
            )
            logger.info("Sistema de IA de NPCs inicializado")

            # Agregar efecto de IA de NPCs hostiles
            self.game_tick.add_effect(
                NPCAIEffect(self.npc_service, self.npc_ai_service, interval_seconds=2.0)
            )
            logger.info("Efecto de IA de NPCs hostiles habilitado")

            # Iniciar el sistema de tick después de agregar todos los efectos
            self.game_tick.start()
            logger.info("Sistema de tick del juego iniciado con todos los efectos")

            # Inicializar configuración de efectos en Redis (si no existe)
            await self._initialize_effects_config()

            # Cargar ground items desde Redis para todos los mapas activos
            await self._load_ground_items()

        except redis.ConnectionError as e:
            logger.error("No se pudo conectar a Redis: %s", e)  # noqa: TRY400
            logger.error(  # noqa: TRY400
                "El servidor requiere Redis para funcionar. "
                "Asegúrate de que Redis esté ejecutándose."
            )
            logger.error("Puedes iniciar Redis con: redis-server")  # noqa: TRY400
            sys.exit(1)
        except Exception:
            logger.exception("Error inesperado al conectar con Redis")
            sys.exit(1)

        self.server = await asyncio.start_server(
            self.handle_client,
            self.host,
            self.port,
        )

        addrs = ", ".join(str(sock.getsockname()) for sock in self.server.sockets)
        logger.info("Servidor escuchando en %s", addrs)

        async with self.server:
            await self.server.serve_forever()

    async def stop(self) -> None:
        """Detiene el servidor."""
        # Detener sistema de tick del juego
        if self.game_tick:
            await self.game_tick.stop()
            logger.info("Sistema de tick del juego detenido")

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Servidor detenido")

        # Desconectar de Redis
        if self.redis_client:
            await self.redis_client.disconnect()
