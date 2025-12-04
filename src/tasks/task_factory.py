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
from src.tasks.clan.task_leave_clan import TaskLeaveClan
from src.tasks.clan.task_request_clan_details import TaskRequestClanDetails
from src.tasks.commerce.task_commerce_buy import TaskCommerceBuy
from src.tasks.commerce.task_commerce_end import TaskCommerceEnd
from src.tasks.commerce.task_commerce_sell import TaskCommerceSell
from src.tasks.commerce.task_commerce_start import TaskCommerceStart
from src.tasks.commerce.task_user_commerce_confirm import TaskUserCommerceConfirm
from src.tasks.commerce.task_user_commerce_end import TaskUserCommerceEnd
from src.tasks.commerce.task_user_commerce_offer import TaskUserCommerceOffer
from src.tasks.commerce.task_user_commerce_ok import TaskUserCommerceOk
from src.tasks.commerce.task_user_commerce_reject import TaskUserCommerceReject
from src.tasks.handler_registry import HandlerRegistry
from src.tasks.interaction.task_information import TaskInformation
from src.tasks.interaction.task_left_click import TaskLeftClick
from src.tasks.interaction.task_pickup import TaskPickup
from src.tasks.interaction.task_talk import TaskTalk
from src.tasks.inventory.task_double_click import TaskDoubleClick
from src.tasks.inventory.task_drop import TaskDrop
from src.tasks.inventory.task_equip_item import TaskEquipItem
from src.tasks.inventory.task_inventory_click import TaskInventoryClick
from src.tasks.inventory.task_use_item import TaskUseItem
from src.tasks.player.task_account import TaskCreateAccount
from src.tasks.player.task_attack import TaskAttack
from src.tasks.player.task_attributes import TaskRequestAttributes
from src.tasks.player.task_change_heading import TaskChangeHeading
from src.tasks.player.task_login import TaskLogin
from src.tasks.player.task_meditate import TaskMeditate
from src.tasks.player.task_request_position_update import TaskRequestPositionUpdate
from src.tasks.player.task_request_stats import TaskRequestStats
from src.tasks.player.task_walk import TaskWalk
from src.tasks.spells.task_cast_spell import TaskCastSpell
from src.tasks.spells.task_move_spell import TaskMoveSpell
from src.tasks.spells.task_spell_info import TaskSpellInfo
from src.tasks.task_ayuda import TaskAyuda
from src.tasks.task_dice import TaskDice
from src.tasks.task_motd import TaskMotd
from src.tasks.task_null import TaskNull
from src.tasks.task_online import TaskOnline
from src.tasks.task_party_accept_member import TaskPartyAcceptMember
from src.tasks.task_party_create import TaskPartyCreate
from src.tasks.task_party_join import TaskPartyJoin
from src.tasks.task_party_kick import TaskPartyKick
from src.tasks.task_party_leave import TaskPartyLeave
from src.tasks.task_party_message import TaskPartyMessage
from src.tasks.task_party_set_leader import TaskPartySetLeader
from src.tasks.task_ping import TaskPing
from src.tasks.task_quit import TaskQuit
from src.tasks.task_request_skills import TaskRequestSkills
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
        self.handlers = HandlerRegistry(deps)

    def create_task(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None = None,
    ) -> Task:
        """Crea una Task apropiada basada en el packet_id.

        Args:
            data: Datos del packet recibido.
            message_sender: Enviador de mensajes para el cliente.
            session_data: Datos de sesión compartidos entre tasks.

        Returns:
            Instancia de Task correspondiente al packet_id.
        """
        # Detectar TLS handshake antes de leer packet_id
        if self._looks_like_tls_handshake(data, message_sender):
            return TaskTLSHandshake(data, message_sender)

        # Leer packet_id del primer byte
        packet_id = data[0] if data else 0

        # Buscar la clase de task en el mapa
        task_class = TASK_HANDLERS.get(packet_id)
        if task_class is None:
            client_address = message_sender.connection.address
            logger.warning(
                "Packet_id=%d no implementado desde %s. Retornando TaskNull.",
                packet_id,
                client_address,
            )
            return TaskNull(data, message_sender)

        # Pre-validar packet si está habilitado
        parsed_data: dict[str, Any] = {}
        if self.enable_prevalidation:
            validation_result = self._prevalidate_packet(data, packet_id, message_sender)
            if validation_result is not None:
                if not validation_result.success:
                    # Packet inválido, retornar TaskNull para ignorarlo
                    return TaskNull(data, message_sender)
                # Si validación fue exitosa, extraer datos parseados
                parsed_data = validation_result.data or {}

        # Crear la task con las dependencias apropiadas
        return self._create_task_with_deps(
            task_class, data, message_sender, session_data, parsed_data
        )

    def _create_task_with_deps(
        self,
        task_class: type[Task],
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None,
        parsed_data: dict[str, Any],
    ) -> Task:
        """Crea una task inyectando las dependencias necesarias.

        Args:
            task_class: Clase de la task a crear.
            data: Datos del packet.
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión.
            parsed_data: Datos pre-validados del packet.

        Returns:
            Instancia de la task con dependencias inyectadas.
        """
        h = self.handlers  # Alias corto

        # Tasks que necesitan datos parseados del validador
        if parsed_data:
            # TaskInventoryClick (packet_id 137) - requiere slot validado
            if task_class == TaskInventoryClick and "slot" in parsed_data:
                return TaskInventoryClick(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    inventory_click_handler=h.get("inventory_click", message_sender, session_data),
                    session_data=session_data,
                )

            # TaskUseItem (packet_id 138) - requiere slot validado
            if task_class == TaskUseItem and "slot" in parsed_data:
                return TaskUseItem(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    use_item_handler=h.get("use_item", message_sender, session_data),
                    player_repo=self.deps.player_repo,
                    session_data=session_data,
                )

            # TaskCommerceBuy (packet_id 128) - requiere slot y amount
            if task_class == TaskCommerceBuy and "slot" in parsed_data and "amount" in parsed_data:
                return TaskCommerceBuy(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    amount=parsed_data["amount"],
                    commerce_buy_handler=h.get("commerce_buy", message_sender, session_data),
                    session_data=session_data,
                )

            # TaskCommerceSell (packet_id 129) - requiere slot y amount
            if task_class == TaskCommerceSell and "slot" in parsed_data and "amount" in parsed_data:
                return TaskCommerceSell(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    amount=parsed_data["amount"],
                    commerce_sell_handler=h.get("commerce_sell", message_sender, session_data),
                    session_data=session_data,
                )

            # TaskBankExtractGold (packet_id 111) - recibe amount
            if task_class == TaskBankExtractGold and "amount" in parsed_data:
                handler = h.get("bank_extract_gold", message_sender, session_data)
                return TaskBankExtractGold(
                    data=data,
                    message_sender=message_sender,
                    amount=parsed_data["amount"],
                    bank_extract_gold_handler=handler,
                    session_data=session_data,
                )

            # TaskBankDepositGold (packet_id 112) - recibe amount
            if task_class == TaskBankDepositGold and "amount" in parsed_data:
                handler = h.get("bank_deposit_gold", message_sender, session_data)
                return TaskBankDepositGold(
                    data=data,
                    message_sender=message_sender,
                    amount=parsed_data["amount"],
                    bank_deposit_gold_handler=handler,
                    session_data=session_data,
                )

        # Mapeo de task_class a función constructora con dependencias
        task_factories: dict[type, Callable[[], Task]] = {
            TaskLogin: lambda: TaskLogin(
                data,
                message_sender,
                login_handler=h.get("login", message_sender, session_data),
                session_data=session_data,
            ),
            TaskCreateAccount: lambda: TaskCreateAccount(
                data,
                message_sender,
                create_account_handler=h.get("create_account", message_sender, session_data),
                session_data=session_data,
            ),
            TaskDice: lambda: TaskDice(
                data,
                message_sender,
                dice_handler=h.get("dice", message_sender, session_data),
                session_data=session_data,
                server_repo=self.deps.server_repo,
            ),
            TaskRequestAttributes: lambda: TaskRequestAttributes(
                data,
                message_sender,
                request_attributes_handler=h.get(
                    "request_attributes", message_sender, session_data
                ),
                session_data=session_data,
            ),
            TaskRequestSkills: lambda: TaskRequestSkills(
                data,
                message_sender,
                request_skills_handler=h.get("request_skills", message_sender, session_data),
                session_data=session_data,
            ),
            TaskTalk: lambda: TaskTalk(
                data,
                message_sender,
                talk_handler=h.get("talk", message_sender, session_data),
                session_data=session_data,
            ),
            TaskWalk: lambda: TaskWalk(
                data,
                message_sender,
                h.get("walk", message_sender, session_data),
                session_data,
            ),
            TaskGMCommands: lambda: TaskGMCommands(
                data,
                message_sender,
                gm_command_handler=h.get("gm_command", message_sender, session_data),
                session_data=session_data,
            ),
            TaskChangeHeading: lambda: TaskChangeHeading(
                data,
                message_sender,
                change_heading_handler=h.get("change_heading", message_sender, session_data),
                session_data=session_data,
            ),
            TaskMeditate: lambda: TaskMeditate(
                data,
                message_sender,
                meditate_handler=h.get("meditate", message_sender, session_data),
                session_data=session_data,
            ),
            TaskRequestStats: lambda: TaskRequestStats(
                data,
                message_sender,
                request_stats_handler=h.get("request_stats", message_sender, session_data),
                session_data=session_data,
            ),
            TaskRequestPositionUpdate: lambda: TaskRequestPositionUpdate(
                data,
                message_sender,
                request_position_update_handler=h.get(
                    "request_position_update", message_sender, session_data
                ),
                session_data=session_data,
            ),
            TaskOnline: lambda: TaskOnline(
                data,
                message_sender,
                online_handler=h.get("online", message_sender, session_data),
                session_data=session_data,
            ),
            TaskMotd: lambda: TaskMotd(
                data,
                message_sender,
                motd_handler=h.get("motd", message_sender, session_data),
            ),
            TaskInformation: lambda: TaskInformation(
                data,
                message_sender,
                information_handler=h.get("information", message_sender, session_data),
            ),
            TaskUptime: lambda: TaskUptime(
                data,
                message_sender,
                uptime_handler=h.get("uptime", message_sender, session_data),
            ),
            TaskQuit: lambda: TaskQuit(
                data,
                message_sender,
                quit_handler=h.get("quit", message_sender, session_data),
                session_data=session_data,
            ),
            TaskDoubleClick: lambda: TaskDoubleClick(
                data,
                message_sender,
                double_click_handler=h.get("double_click", message_sender, session_data),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskLeftClick: lambda: TaskLeftClick(
                data,
                message_sender,
                left_click_handler=h.get("left_click", message_sender, session_data),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskEquipItem: lambda: TaskEquipItem(
                data,
                message_sender,
                equip_item_handler=h.get("equip_item", message_sender, session_data),
                session_data=session_data,
            ),
            TaskAttack: lambda: TaskAttack(
                data,
                message_sender,
                attack_handler=h.get("attack", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPickup: lambda: TaskPickup(
                data,
                message_sender,
                pickup_handler=h.get("pickup", message_sender, session_data),
                session_data=session_data,
            ),
            TaskDrop: lambda: TaskDrop(
                data,
                message_sender,
                drop_handler=h.get("drop", message_sender, session_data),
                session_data=session_data,
            ),
            TaskBankDeposit: lambda: TaskBankDeposit(
                data,
                message_sender,
                bank_deposit_handler=h.get("bank_deposit", message_sender, session_data),
                session_data=session_data,
            ),
            TaskBankExtract: lambda: TaskBankExtract(
                data,
                message_sender,
                bank_extract_handler=h.get("bank_extract", message_sender, session_data),
                session_data=session_data,
            ),
            TaskBankEnd: lambda: TaskBankEnd(
                data,
                message_sender,
                bank_end_handler=h.get("bank_end", message_sender, session_data),
                session_data=session_data,
            ),
            TaskCommerceEnd: lambda: TaskCommerceEnd(
                data,
                message_sender,
                commerce_end_handler=h.get("commerce_end", message_sender, session_data),
            ),
            TaskCommerceStart: lambda: TaskCommerceStart(
                data,
                message_sender,
            ),
            TaskAyuda: lambda: TaskAyuda(
                data,
                message_sender,
                ayuda_handler=h.get("ayuda", message_sender, session_data),
            ),
            TaskPing: lambda: TaskPing(
                data,
                message_sender,
                ping_handler=h.get("ping", message_sender, session_data),
            ),
            TaskPartyCreate: lambda: TaskPartyCreate(
                data,
                message_sender,
                party_create_handler=h.get("party_create", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPartyJoin: lambda: TaskPartyJoin(
                data,
                message_sender,
                party_join_handler=h.get("party_join", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPartyAcceptMember: lambda: TaskPartyAcceptMember(
                data,
                message_sender,
                party_accept_handler=h.get("party_accept", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPartyLeave: lambda: TaskPartyLeave(
                data,
                message_sender,
                party_leave_handler=h.get("party_leave", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPartyMessage: lambda: TaskPartyMessage(
                data,
                message_sender,
                party_message_handler=h.get("party_message", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPartyKick: lambda: TaskPartyKick(
                data,
                message_sender,
                party_kick_handler=h.get("party_kick", message_sender, session_data),
                session_data=session_data,
            ),
            TaskPartySetLeader: lambda: TaskPartySetLeader(
                data,
                message_sender,
                party_set_leader_handler=h.get("party_set_leader", message_sender, session_data),
                session_data=session_data,
            ),
            TaskLeaveClan: lambda: TaskLeaveClan(
                data,
                message_sender,
                leave_clan_handler=h.get("leave_clan", message_sender, session_data),
                session_data=session_data,
            ),
            TaskRequestClanDetails: lambda: TaskRequestClanDetails(
                data,
                message_sender,
                request_clan_details_handler=h.get(
                    "request_clan_details", message_sender, session_data
                ),
                session_data=session_data,
            ),
            TaskUserCommerceOffer: lambda: TaskUserCommerceOffer(
                data,
                message_sender,
                trade_offer_handler=h.get("trade_offer", message_sender, session_data),
                session_data=session_data,
            ),
            TaskUserCommerceOk: lambda: TaskUserCommerceOk(
                data,
                message_sender,
                trade_update_handler=h.get("trade_update", message_sender, session_data),
                session_data=session_data,
            ),
            TaskUserCommerceReject: lambda: TaskUserCommerceReject(
                data,
                message_sender,
                trade_update_handler=h.get("trade_update", message_sender, session_data),
                session_data=session_data,
            ),
            TaskUserCommerceConfirm: lambda: TaskUserCommerceConfirm(
                data,
                message_sender,
                trade_update_handler=h.get("trade_update", message_sender, session_data),
                session_data=session_data,
            ),
            TaskUserCommerceEnd: lambda: TaskUserCommerceEnd(
                data,
                message_sender,
                trade_update_handler=h.get("trade_update", message_sender, session_data),
                session_data=session_data,
            ),
            TaskWork: lambda: TaskWork(
                data,
                message_sender,
                work_handler=h.get("work", message_sender, session_data),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskWorkLeftClick: lambda: TaskWorkLeftClick(
                data,
                message_sender,
                work_left_click_handler=h.get("work_left_click", message_sender, session_data),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskMoveSpell: lambda: TaskMoveSpell(
                data,
                message_sender,
                move_spell_handler=h.get("move_spell", message_sender, session_data),
                session_data=session_data,
            ),
            TaskSpellInfo: lambda: TaskSpellInfo(
                data,
                message_sender,
                spell_info_handler=h.get("spell_info", message_sender, session_data),
                session_data=session_data,
            ),
            TaskCastSpell: lambda: TaskCastSpell(
                data,
                message_sender,
                h.get("cast_spell", message_sender, session_data),
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
