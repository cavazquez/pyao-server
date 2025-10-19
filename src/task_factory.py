"""Factory para crear instancias de Tasks con sus dependencias."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from src.packet_handlers import TASK_HANDLERS
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
    from src.message_sender import MessageSender
    from src.task import Task


class TaskFactory:
    """Factory para crear instancias de Tasks con sus dependencias inyectadas."""

    def __init__(self, deps: DependencyContainer) -> None:
        """Inicializa el factory con el contenedor de dependencias.

        Args:
            deps: Contenedor con todas las dependencias del servidor.
        """
        self.deps = deps

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
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)

        # Mapeo de task_class a función constructora con dependencias
        task_factories: dict[type, Callable[[], Task]] = {
            TaskLogin: lambda: TaskLogin(
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
            ),
            TaskCreateAccount: lambda: TaskCreateAccount(
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
            ),
            TaskDice: lambda: TaskDice(data, message_sender, session_data, self.deps.server_repo),
            TaskRequestAttributes: lambda: TaskRequestAttributes(
                data, message_sender, self.deps.player_repo, session_data
            ),
            TaskTalk: lambda: TaskTalk(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.account_repo,
                self.deps.map_manager,
                session_data,
            ),
            TaskWalk: lambda: TaskWalk(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                session_data,
            ),
            TaskChangeHeading: lambda: TaskChangeHeading(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.account_repo,
                self.deps.map_manager,
                session_data,
            ),
            TaskRequestStats: lambda: TaskRequestStats(
                data, message_sender, self.deps.player_repo, session_data
            ),
            TaskRequestPositionUpdate: lambda: TaskRequestPositionUpdate(
                data, message_sender, self.deps.player_repo, session_data
            ),
            TaskOnline: lambda: TaskOnline(
                data, message_sender, self.deps.map_manager, session_data
            ),
            TaskMotd: lambda: TaskMotd(data, message_sender, self.deps.server_repo),
            TaskInformation: lambda: TaskInformation(
                data, message_sender, self.deps.server_repo, self.deps.map_manager
            ),
            TaskUptime: lambda: TaskUptime(data, message_sender, self.deps.server_repo),
            TaskQuit: lambda: TaskQuit(
                data, message_sender, self.deps.player_repo, self.deps.map_manager, session_data
            ),
            TaskDoubleClick: lambda: TaskDoubleClick(
                data, message_sender, self.deps.player_repo, self.deps.map_manager, session_data
            ),
            TaskLeftClick: lambda: TaskLeftClick(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.map_manager,
                self.deps.merchant_repo,
                self.deps.bank_repo,
                self.deps.redis_client,
                session_data,
            ),
            TaskCastSpell: lambda: TaskCastSpell(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.spell_service,
                session_data,
                self.deps.spellbook_repo,
            ),
            TaskMeditate: lambda: TaskMeditate(
                data, message_sender, self.deps.player_repo, session_data
            ),
            TaskInventoryClick: lambda: TaskInventoryClick(
                data, message_sender, self.deps.player_repo, session_data, self.deps.equipment_repo
            ),
            TaskEquipItem: lambda: TaskEquipItem(
                data, message_sender, self.deps.player_repo, session_data, self.deps.equipment_repo
            ),
            TaskAttack: lambda: TaskAttack(
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
            ),
            TaskPickup: lambda: TaskPickup(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                self.deps.item_catalog,
                session_data,
            ),
            TaskDrop: lambda: TaskDrop(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                session_data,
            ),
            TaskCommerceBuy: lambda: TaskCommerceBuy(
                data,
                message_sender,
                self.deps.commerce_service,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.redis_client,
                session_data,
            ),
            TaskCommerceSell: lambda: TaskCommerceSell(
                data,
                message_sender,
                self.deps.commerce_service,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.redis_client,
                session_data,
            ),
            TaskBankDeposit: lambda: TaskBankDeposit(
                data,
                message_sender,
                self.deps.bank_repo,
                self.deps.inventory_repo,
                self.deps.player_repo,
                session_data,
            ),
            TaskBankExtract: lambda: TaskBankExtract(
                data,
                message_sender,
                self.deps.bank_repo,
                self.deps.inventory_repo,
                self.deps.player_repo,
                session_data,
            ),
            TaskBankEnd: lambda: TaskBankEnd(data, message_sender, session_data),
            TaskCommerceEnd: lambda: TaskCommerceEnd(data, message_sender),
        }

        # Buscar factory en el diccionario y ejecutarla
        factory = task_factories.get(task_class)
        if factory:
            return factory()

        # Fallback para tasks sin dependencias especiales
        return task_class(data, message_sender)
