"""Servidor TCP para Argentum Online."""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

import redis
from src.client_connection import ClientConnection
from src.message_sender import MessageSender
from src.packet_handlers import TASK_HANDLERS
from src.server_initializer import ServerInitializer
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
    from src.dependency_container import DependencyContainer
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
        self.host = host
        self.port = port
        self.server: asyncio.Server | None = None
        self.deps: DependencyContainer | None = None  # Contenedor de dependencias

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

        if not self.deps:
            return TaskNull(data, message_sender)

        packet_id = data[0]

        # Buscar handler en el diccionario
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)

        # Pasar parámetros adicionales según el tipo de tarea
        if task_class is TaskLogin:
            return TaskLogin(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.account_repo,
                self.deps.map_manager,
                session_data,
                self.deps.npc_service,
                self.deps.server_repo,
                self.deps.spellbook_repo,
                self.deps.spell_catalog,
                self.deps.equipment_repo,
            )
        if task_class is TaskCreateAccount:
            return TaskCreateAccount(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.account_repo,
                self.deps.map_manager,
                session_data,
                self.deps.npc_service,
                self.deps.server_repo,
                self.deps.spellbook_repo,
                self.deps.spell_catalog,
                self.deps.equipment_repo,
            )
        if task_class is TaskDice:
            return TaskDice(data, message_sender, session_data, self.deps.server_repo)
        if task_class is TaskRequestAttributes:
            return TaskRequestAttributes(data, message_sender, self.deps.player_repo, session_data)
        if task_class is TaskTalk:
            return TaskTalk(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.account_repo,
                self.deps.map_manager,
                session_data,
            )
        if task_class is TaskWalk:
            return TaskWalk(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                session_data,
            )
        if task_class is TaskChangeHeading:
            return TaskChangeHeading(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.account_repo,
                self.deps.map_manager,
                session_data,
            )
        if task_class is TaskRequestStats:
            return TaskRequestStats(data, message_sender, self.deps.player_repo, session_data)
        if task_class is TaskRequestPositionUpdate:
            return TaskRequestPositionUpdate(
                data, message_sender, self.deps.player_repo, session_data
            )
        if task_class is TaskOnline:
            return TaskOnline(data, message_sender, self.deps.map_manager, session_data)
        if task_class is TaskMotd:
            return TaskMotd(data, message_sender, self.deps.server_repo)
        if task_class is TaskInformation:
            return TaskInformation(
                data, message_sender, self.deps.server_repo, self.deps.map_manager
            )
        if task_class is TaskUptime:
            return TaskUptime(data, message_sender, self.deps.server_repo)
        if task_class is TaskQuit:
            return TaskQuit(
                data, message_sender, self.deps.player_repo, self.deps.map_manager, session_data
            )
        if task_class is TaskDoubleClick:
            return TaskDoubleClick(
                data, message_sender, self.deps.player_repo, self.deps.map_manager, session_data
            )
        if task_class is TaskLeftClick:
            return TaskLeftClick(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.map_manager,
                self.deps.merchant_repo,
                self.deps.bank_repo,
                self.deps.redis_client,
                session_data,
            )
        if task_class is TaskCastSpell:
            return TaskCastSpell(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.spell_service,
                session_data,
                self.deps.spellbook_repo,
            )
        if task_class is TaskMeditate:
            return TaskMeditate(data, message_sender, self.deps.player_repo, session_data)
        if task_class is TaskInventoryClick:
            return TaskInventoryClick(
                data, message_sender, self.deps.player_repo, session_data, self.deps.equipment_repo
            )
        if task_class is TaskEquipItem:
            return TaskEquipItem(
                data, message_sender, self.deps.player_repo, session_data, self.deps.equipment_repo
            )
        if task_class is TaskAttack:
            return TaskAttack(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.combat_service,
                self.deps.map_manager,
                self.deps.npc_service,
                self.deps.broadcast_service,
                self.deps.npc_respawn_service,
                self.deps.loot_table_service,
                self.deps.item_catalog,
                session_data,
            )
        if task_class is TaskPickup:
            return TaskPickup(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                self.deps.item_catalog,
                session_data,
            )
        if task_class is TaskDrop:
            return TaskDrop(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                session_data,
            )
        if task_class is TaskCommerceBuy:
            return TaskCommerceBuy(
                data,
                message_sender,
                self.deps.commerce_service,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.redis_client,
                session_data,
            )
        if task_class is TaskCommerceSell:
            return TaskCommerceSell(
                data,
                message_sender,
                self.deps.commerce_service,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.redis_client,
                session_data,
            )
        if task_class is TaskBankDeposit:
            return TaskBankDeposit(
                data,
                message_sender,
                self.deps.bank_repo,
                self.deps.inventory_repo,
                self.deps.player_repo,
                session_data,
            )
        if task_class is TaskBankExtract:
            return TaskBankExtract(
                data,
                message_sender,
                self.deps.bank_repo,
                self.deps.inventory_repo,
                self.deps.player_repo,
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
        if self.deps and self.deps.redis_client:
            await self.deps.redis_client.increment_connections()
            connections = await self.deps.redis_client.get_connections_count()
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
            if "user_id" in session_data and self.deps and self.deps.player_repo:
                user_id_value = session_data["user_id"]
                if not isinstance(user_id_value, dict):
                    user_id = int(user_id_value)

                    # Obtener el mapa del jugador antes de removerlo
                    position = await self.deps.player_repo.get_position(user_id)
                    if position:
                        map_id = position["map"]

                        # Enviar CHARACTER_REMOVE a todos los jugadores en el mapa
                        other_senders = self.deps.map_manager.get_all_message_senders_in_map(
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

                    # Remover jugador del mapa
                    self.deps.map_manager.remove_player(user_id)

            connection.close()
            await connection.wait_closed()

            # Decrementar contador de conexiones en Redis
            if self.deps and self.deps.redis_client:
                await self.deps.redis_client.decrement_connections()
                connections = await self.deps.redis_client.get_connections_count()
                logger.info("Conexiones activas: %d", connections)

    async def start(self) -> None:
        """Inicia el servidor TCP."""
        try:
            # Inicializar todas las dependencias usando ServerInitializer
            initializer = ServerInitializer()
            self.deps, self.host, self.port = await initializer.initialize_all()

            # Iniciar el sistema de tick
            self.deps.game_tick.start()
            logger.info("✓ Sistema de tick del juego iniciado")

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
        if self.deps and self.deps.game_tick:
            await self.deps.game_tick.stop()
            logger.info("Sistema de tick del juego detenido")

        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("Servidor detenido")

        # Desconectar de Redis
        if self.deps and self.deps.redis_client:
            await self.deps.redis_client.disconnect()
