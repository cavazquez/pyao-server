"""Factory para crear instancias de Tasks con sus dependencias."""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.network.packet_handlers import TASK_HANDLERS
from src.network.packet_reader import PacketReader
from src.network.packet_validator import PacketValidator
from src.tasks.admin.task_gm_commands import TaskGMCommands
from src.tasks.banking.task_bank_deposit import TaskBankDeposit
from src.tasks.banking.task_bank_deposit_gold import TaskBankDepositGold
from src.tasks.banking.task_bank_end import TaskBankEnd
from src.tasks.banking.task_bank_extract import TaskBankExtract
from src.tasks.banking.task_bank_extract_gold import TaskBankExtractGold
from src.tasks.commerce.task_commerce_buy import TaskCommerceBuy
from src.tasks.commerce.task_commerce_end import TaskCommerceEnd
from src.tasks.commerce.task_commerce_sell import TaskCommerceSell
from src.tasks.interaction.task_information import TaskInformation
from src.tasks.interaction.task_left_click import TaskLeftClick
from src.tasks.interaction.task_pickup import TaskPickup
from src.tasks.interaction.task_talk import TaskTalk
from src.tasks.inventory.task_double_click import TaskDoubleClick
from src.tasks.inventory.task_drop import TaskDrop
from src.tasks.inventory.task_equip_item import TaskEquipItem
from src.tasks.inventory.task_inventory_click import TaskInventoryClick
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_attack import TaskAttack
from src.tasks.player.task_attributes import TaskRequestAttributes
from src.tasks.player.task_change_heading import TaskChangeHeading
from src.tasks.player.task_login import TaskLogin
from src.tasks.player.task_request_position_update import TaskRequestPositionUpdate
from src.tasks.player.task_request_stats import TaskRequestStats
from src.tasks.player.task_walk import TaskWalk
from src.tasks.spells.task_move_spell import TaskMoveSpell
from src.tasks.spells.task_spell_info import TaskSpellInfo
from src.tasks.task_dice import TaskDice
from src.tasks.task_motd import TaskMotd
from src.tasks.task_null import TaskNull
from src.tasks.task_online import TaskOnline
from src.tasks.task_quit import TaskQuit
from src.tasks.task_tls_handshake import TaskTLSHandshake
from src.tasks.task_uptime import TaskUptime
from src.tasks.work.task_work import TaskWork
from src.tasks.work.task_work_left_click import TaskWorkLeftClick

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer
    from src.messaging.message_sender import MessageSender
    from src.tasks.task import Task

logger = logging.getLogger(__name__)

TLS_HEADER_MIN_LENGTH = 3
TLS_CONTENT_TYPE_HANDSHAKE = 0x16
TLS_PROTOCOL_MAJOR_VERSION = 0x03
TLS_CLIENT_HELLO_MINOR_VERSIONS = {0x00, 0x01, 0x02, 0x03, 0x04}


class TaskFactory:
    """Factory para crear instancias de Tasks con sus dependencias inyectadas."""

    def __init__(self, deps: DependencyContainer, enable_prevalidation: bool = True) -> None:
        """Inicializa el factory con el contenedor de dependencias.

        Args:
            deps: Contenedor con todas las dependencias del servidor.
            enable_prevalidation: Si True, pre-valida packets antes de crear tasks.
        """
        self.deps = deps
        self.enable_prevalidation = enable_prevalidation

    def create_task(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int]],
    ) -> Task:
        """Crea la tarea apropiada según el PacketID recibido.

        Si enable_prevalidation=True, pre-valida el packet antes de crear la task.
        En caso de error de validación, envía el error al cliente y retorna TaskNull.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
            session_data: Datos de sesión (mutable, compartido entre tareas).

        Returns:
            Instancia de la tarea correspondiente.
        """
        if len(data) == 0:
            return TaskNull(data, message_sender)

        if self._looks_like_tls_handshake(data, message_sender):
            return TaskTLSHandshake(data, message_sender)

        packet_id = data[0]
        task_class = TASK_HANDLERS.get(packet_id, TaskNull)

        # Pre-validación opcional (si está habilitada)
        parsed_data = None
        if self.enable_prevalidation:
            validation_result = self._prevalidate_packet(data, packet_id, message_sender)
            if validation_result is not None and not validation_result.success:
                # Validación falló, retornar TaskNull
                return TaskNull(data, message_sender)
            # Si la validación pasó, extraer datos
            if validation_result is not None and validation_result.success:
                parsed_data = validation_result.data

        # Manejar tasks refactorizadas que reciben datos validados directamente
        if parsed_data is not None:
            # TaskCommerceSell (packet_id 42) - recibe slot y quantity
            if (
                task_class == TaskCommerceSell
                and "slot" in parsed_data
                and "quantity" in parsed_data
            ):
                return TaskCommerceSell(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    quantity=parsed_data["quantity"],
                    commerce_service=self.deps.commerce_service,
                    player_repo=self.deps.player_repo,
                    inventory_repo=self.deps.inventory_repo,
                    redis_client=self.deps.redis_client,
                    session_data=session_data,
                )

            # TaskCommerceBuy (packet_id 40) - recibe slot y quantity
            if (
                task_class == TaskCommerceBuy
                and "slot" in parsed_data
                and "quantity" in parsed_data
            ):
                return TaskCommerceBuy(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    quantity=parsed_data["quantity"],
                    commerce_service=self.deps.commerce_service,
                    player_repo=self.deps.player_repo,
                    inventory_repo=self.deps.inventory_repo,
                    redis_client=self.deps.redis_client,
                    session_data=session_data,
                )

            # TaskInventoryClick (packet_id 23) - recibe slot
            if task_class == TaskInventoryClick and "slot" in parsed_data:
                return TaskInventoryClick(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    player_repo=self.deps.player_repo,
                    session_data=session_data,
                    equipment_repo=self.deps.equipment_repo,
                )

            # TaskMoveSpell (packet_id 45) - recibe slot y upwards
            if task_class == TaskMoveSpell and "slot" in parsed_data and "upwards" in parsed_data:
                return TaskMoveSpell(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    upwards=parsed_data["upwards"],
                    session_data=session_data,
                    spellbook_repo=self.deps.spellbook_repo,
                    spell_catalog=self.deps.spell_catalog,
                )

            # TaskSpellInfo (packet_id 35) - recibe slot
            if task_class == TaskSpellInfo and "slot" in parsed_data:
                return TaskSpellInfo(
                    data=data,
                    message_sender=message_sender,
                    spellbook_repo=self.deps.spellbook_repo,
                    spell_catalog=self.deps.spell_catalog,
                    session_data=session_data,
                    slot=parsed_data["slot"],
                )

            # TaskBankExtractGold (packet_id 111) - recibe amount
            if task_class == TaskBankExtractGold and "amount" in parsed_data:
                return TaskBankExtractGold(
                    data=data,
                    message_sender=message_sender,
                    amount=parsed_data["amount"],
                    bank_repo=self.deps.bank_repo,
                    player_repo=self.deps.player_repo,
                    session_data=session_data,
                )

            # TaskBankDepositGold (packet_id 112) - recibe amount
            if task_class == TaskBankDepositGold and "amount" in parsed_data:
                return TaskBankDepositGold(
                    data=data,
                    message_sender=message_sender,
                    amount=parsed_data["amount"],
                    bank_repo=self.deps.bank_repo,
                    player_repo=self.deps.player_repo,
                    session_data=session_data,
                )

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
                self.deps.player_map_service,
                self.deps.npc_world_manager,
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
                self.deps.stamina_service,
                self.deps.player_map_service,
                session_data,
            ),
            TaskGMCommands: lambda: TaskGMCommands(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.map_manager,
                self.deps.broadcast_service,
                self.deps.player_map_service,
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
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.map_manager,
                self.deps.inventory_repo,
                session_data,
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
                self.deps.map_resources_service,
            ),
            # TaskInventoryClick: manejada arriba con datos validados
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
                self.deps.npc_death_service,  # Agregar NPCDeathService
                self.deps.npc_respawn_service,
                self.deps.loot_table_service,
                self.deps.item_catalog,
                self.deps.stamina_service,
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
            # TaskCommerceBuy: manejada arriba con datos validados
            # TaskCommerceSell: manejada arriba con datos validados
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
            TaskWork: lambda: TaskWork(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.map_manager,
                session_data,
                self.deps.map_resources_service,
            ),
            TaskWorkLeftClick: lambda: TaskWorkLeftClick(
                data,
                message_sender,
                self.deps.player_repo,
                self.deps.inventory_repo,
                self.deps.map_manager,
                session_data,
                self.deps.map_resources_service,
            ),
            TaskMoveSpell: lambda: TaskMoveSpell(
                data,
                message_sender,
                session_data=session_data,
                spellbook_repo=self.deps.spellbook_repo,
                spell_catalog=self.deps.spell_catalog,
            ),
            TaskSpellInfo: lambda: TaskSpellInfo(
                data,
                message_sender,
                self.deps.spellbook_repo,
                self.deps.spell_catalog,
                session_data,
            ),
        }

        # Buscar factory en el diccionario y ejecutarla
        factory = task_factories.get(task_class)
        if factory:
            return factory()

        # Fallback para tasks sin dependencias especiales
        return task_class(data, message_sender)

    @staticmethod
    def _prevalidate_packet(data: bytes, packet_id: int, message_sender: MessageSender) -> Any:  # noqa: ANN401 - ValidationResult es genérico, Any es apropiado aquí
        """Pre-valida un packet antes de crear la task.

        Args:
            data: Datos del packet.
            packet_id: ID del packet.
            message_sender: MessageSender para enviar errores al cliente.

        Returns:
            ValidationResult si hay validador para este packet, None si no existe.
        """
        try:
            # Crear reader y validator
            reader = PacketReader(data)
            validator = PacketValidator(reader)

            # Intentar validar según el packet_id
            validation_result = validator.validate_packet_by_id(packet_id)

            # Si no hay validador para este packet, retornar None (no validar)
            if validation_result is None:
                return None

            # Obtener nombre del packet para logging
            from src.network.packet_id import ClientPacketID  # noqa: PLC0415

            try:
                packet_name = ClientPacketID(packet_id).name
            except ValueError:
                packet_name = f"UNKNOWN_{packet_id}"

            # Log del resultado
            client_address = message_sender.connection.address
            validation_result.log_validation(packet_name, packet_id, client_address)

            # Si la validación falló, enviar error al cliente
            if not validation_result.success and validation_result.error_message:
                # Crear una tarea asíncrona para enviar el mensaje
                # (no podemos await aquí porque create_task no es async)
                import asyncio  # noqa: PLC0415

                task = asyncio.create_task(
                    message_sender.send_console_msg(validation_result.error_message)
                )
                # Guardar referencia para evitar que sea garbage collected
                task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

            # Validación exitosa o fallida, retornar resultado
            return validation_result  # noqa: TRY300 - Return necesario aquí para claridad

        except Exception:
            # Si hay algún error en la validación, loguear y continuar sin validar
            logger.exception("Error inesperado en pre-validación de packet_id=%d", packet_id)
            return None

    @staticmethod
    def _looks_like_tls_handshake(data: bytes, message_sender: MessageSender) -> bool:
        """Detecta si el paquete parece ser un ClientHello TLS y SSL está deshabilitado.

        Returns:
            bool: True si el paquete coincide con la cabecera de un ClientHello TLS.
        """
        if len(data) < TLS_HEADER_MIN_LENGTH:
            return False

        connection = getattr(message_sender, "connection", None)
        if connection is None:
            return False

        if getattr(connection, "is_ssl_enabled", False):
            return False

        return (
            data[0] == TLS_CONTENT_TYPE_HANDSHAKE
            and data[1] == TLS_PROTOCOL_MAJOR_VERSION
            and data[2] in TLS_CLIENT_HELLO_MINOR_VERSIONS
        )
