"""Factory para crear instancias de Tasks con sus dependencias."""

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from src.command_handlers.attack_handler import AttackCommandHandler
from src.command_handlers.ayuda_handler import AyudaCommandHandler
from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
from src.command_handlers.bank_deposit_handler import BankDepositCommandHandler
from src.command_handlers.bank_end_handler import BankEndCommandHandler
from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
from src.command_handlers.change_heading_handler import ChangeHeadingCommandHandler
from src.command_handlers.commerce_buy_handler import CommerceBuyCommandHandler
from src.command_handlers.commerce_end_handler import CommerceEndCommandHandler
from src.command_handlers.commerce_sell_handler import CommerceSellCommandHandler
from src.command_handlers.create_account_handler import CreateAccountCommandHandler
from src.command_handlers.dice_handler import DiceCommandHandler
from src.command_handlers.double_click_handler import DoubleClickCommandHandler
from src.command_handlers.drop_handler import DropCommandHandler
from src.command_handlers.equip_item_handler import EquipItemCommandHandler
from src.command_handlers.gm_command_handler import GMCommandHandler
from src.command_handlers.information_handler import InformationCommandHandler
from src.command_handlers.inventory_click_handler import InventoryClickCommandHandler
from src.command_handlers.left_click_handler import LeftClickCommandHandler
from src.command_handlers.login_handler import LoginCommandHandler
from src.command_handlers.meditate_handler import MeditateCommandHandler
from src.command_handlers.motd_handler import MotdCommandHandler
from src.command_handlers.move_spell_handler import MoveSpellCommandHandler
from src.command_handlers.online_handler import OnlineCommandHandler
from src.command_handlers.party_accept_handler import PartyAcceptCommandHandler
from src.command_handlers.party_create_handler import PartyCreateCommandHandler
from src.command_handlers.party_join_handler import PartyJoinCommandHandler
from src.command_handlers.party_kick_handler import PartyKickCommandHandler
from src.command_handlers.party_leave_handler import PartyLeaveCommandHandler
from src.command_handlers.party_message_handler import PartyMessageCommandHandler
from src.command_handlers.party_set_leader_handler import PartySetLeaderCommandHandler
from src.command_handlers.pickup_handler import PickupCommandHandler
from src.command_handlers.ping_handler import PingCommandHandler
from src.command_handlers.quit_handler import QuitCommandHandler
from src.command_handlers.request_attributes_handler import RequestAttributesCommandHandler
from src.command_handlers.request_position_update_handler import (
    RequestPositionUpdateCommandHandler,
)
from src.command_handlers.request_skills_handler import RequestSkillsCommandHandler
from src.command_handlers.request_stats_handler import RequestStatsCommandHandler
from src.command_handlers.spell_info_handler import SpellInfoCommandHandler
from src.command_handlers.talk_handler import TalkCommandHandler
from src.command_handlers.uptime_handler import UptimeCommandHandler
from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.command_handlers.walk_handler import WalkCommandHandler
from src.command_handlers.work_handler import WorkCommandHandler
from src.command_handlers.work_left_click_handler import WorkLeftClickCommandHandler
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

        # Crear command handlers (reutilizables, lazy initialization)
        self._attack_handler: AttackCommandHandler | None = None
        self._walk_handler: WalkCommandHandler | None = None
        self._cast_spell_handler: CastSpellCommandHandler | None = None
        self._change_heading_handler: ChangeHeadingCommandHandler | None = None
        self._meditate_handler: MeditateCommandHandler | None = None
        self._use_item_handler: UseItemCommandHandler | None = None
        self._pickup_handler: PickupCommandHandler | None = None
        self._request_attributes_handler: RequestAttributesCommandHandler | None = None
        self._request_position_update_handler: RequestPositionUpdateCommandHandler | None = None
        self._request_skills_handler: RequestSkillsCommandHandler | None = None
        self._request_stats_handler: RequestStatsCommandHandler | None = None
        self._spell_info_handler: SpellInfoCommandHandler | None = None
        self._dice_handler: DiceCommandHandler | None = None
        self._online_handler: OnlineCommandHandler | None = None
        self._information_handler: InformationCommandHandler | None = None
        self._quit_handler: QuitCommandHandler | None = None
        self._uptime_handler: UptimeCommandHandler | None = None
        self._motd_handler: MotdCommandHandler | None = None
        self._ping_handler: PingCommandHandler | None = None
        self._ayuda_handler: AyudaCommandHandler | None = None
        self._commerce_end_handler: CommerceEndCommandHandler | None = None
        self._bank_end_handler: BankEndCommandHandler | None = None
        self._drop_handler: DropCommandHandler | None = None
        self._commerce_buy_handler: CommerceBuyCommandHandler | None = None
        self._commerce_sell_handler: CommerceSellCommandHandler | None = None
        self._bank_deposit_handler: BankDepositCommandHandler | None = None
        self._bank_extract_handler: BankExtractCommandHandler | None = None
        self._bank_deposit_gold_handler: BankDepositGoldCommandHandler | None = None
        self._bank_extract_gold_handler: BankExtractGoldCommandHandler | None = None
        self._equip_item_handler: EquipItemCommandHandler | None = None
        self._work_handler: WorkCommandHandler | None = None
        self._work_left_click_handler: WorkLeftClickCommandHandler | None = None
        self._double_click_handler: DoubleClickCommandHandler | None = None
        self._move_spell_handler: MoveSpellCommandHandler | None = None
        self._inventory_click_handler: InventoryClickCommandHandler | None = None
        self._left_click_handler: LeftClickCommandHandler | None = None
        self._login_handler: LoginCommandHandler | None = None
        self._create_account_handler: CreateAccountCommandHandler | None = None
        self._party_create_handler: PartyCreateCommandHandler | None = None
        self._party_join_handler: PartyJoinCommandHandler | None = None
        self._party_accept_handler: PartyAcceptCommandHandler | None = None
        self._party_leave_handler: PartyLeaveCommandHandler | None = None
        self._party_message_handler: PartyMessageCommandHandler | None = None
        self._party_kick_handler: PartyKickCommandHandler | None = None
        self._party_set_leader_handler: PartySetLeaderCommandHandler | None = None
        self._talk_handler: TalkCommandHandler | None = None
        self._gm_command_handler: GMCommandHandler | None = None

    def _get_attack_handler(self, message_sender: MessageSender) -> AttackCommandHandler:
        """Obtiene o crea el handler de ataque.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de ataque.
        """
        if self._attack_handler is None:
            self._attack_handler = AttackCommandHandler(
                player_repo=self.deps.player_repo,
                combat_service=self.deps.combat_service,
                map_manager=self.deps.map_manager,
                npc_service=self.deps.npc_service,
                broadcast_service=self.deps.broadcast_service,
                npc_death_service=self.deps.npc_death_service,
                npc_respawn_service=self.deps.npc_respawn_service,
                loot_table_service=self.deps.loot_table_service,
                item_catalog=self.deps.item_catalog,
                stamina_service=self.deps.stamina_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._attack_handler.message_sender = message_sender
        return self._attack_handler

    def _get_walk_handler(self, message_sender: MessageSender) -> WalkCommandHandler:
        """Obtiene o crea el handler de movimiento.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de movimiento.
        """
        if self._walk_handler is None:
            self._walk_handler = WalkCommandHandler(
                player_repo=self.deps.player_repo,
                map_manager=self.deps.map_manager,
                broadcast_service=self.deps.broadcast_service,
                stamina_service=self.deps.stamina_service,
                player_map_service=self.deps.player_map_service,
                inventory_repo=self.deps.inventory_repo,
                map_resources=self.deps.map_resources_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._walk_handler.message_sender = message_sender
        return self._walk_handler

    def _get_cast_spell_handler(self, message_sender: MessageSender) -> CastSpellCommandHandler:
        """Obtiene o crea el handler de lanzar hechizo.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de lanzar hechizo.
        """
        if self._cast_spell_handler is None:
            self._cast_spell_handler = CastSpellCommandHandler(
                player_repo=self.deps.player_repo,
                spell_service=self.deps.spell_service,
                spellbook_repo=self.deps.spellbook_repo,
                stamina_service=self.deps.stamina_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._cast_spell_handler.message_sender = message_sender
        return self._cast_spell_handler

    def _get_change_heading_handler(
        self,
        message_sender: MessageSender,
        session_data: dict[str, dict[str, int] | int | str] | None,
    ) -> ChangeHeadingCommandHandler:
        """Obtiene o crea el handler de cambio de dirección.

        Args:
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.

        Returns:
            Handler de cambio de dirección.
        """
        if self._change_heading_handler is None:
            self._change_heading_handler = ChangeHeadingCommandHandler(
                player_repo=self.deps.player_repo,
                account_repo=self.deps.account_repo,
                map_manager=self.deps.map_manager,
                message_sender=message_sender,
                session_data=session_data,
            )
        else:
            # Actualizar message_sender y session_data por si cambiaron
            self._change_heading_handler.message_sender = message_sender
            self._change_heading_handler.session_data = session_data or {}
        return self._change_heading_handler

    def _get_meditate_handler(self, message_sender: MessageSender) -> MeditateCommandHandler:
        """Obtiene o crea el handler de meditación.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de meditación.
        """
        if self._meditate_handler is None:
            self._meditate_handler = MeditateCommandHandler(
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._meditate_handler.message_sender = message_sender
        return self._meditate_handler

    def _get_use_item_handler(self, message_sender: MessageSender) -> UseItemCommandHandler:
        """Obtiene o crea el handler de usar item.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de usar item.
        """
        if self._use_item_handler is None:
            self._use_item_handler = UseItemCommandHandler(
                player_repo=self.deps.player_repo,
                map_resources=self.deps.map_resources_service,
                account_repo=self.deps.account_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._use_item_handler.message_sender = message_sender
        return self._use_item_handler

    def _get_pickup_handler(self, message_sender: MessageSender) -> PickupCommandHandler:
        """Obtiene o crea el handler de recoger item.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de recoger item.
        """
        if self._pickup_handler is None:
            self._pickup_handler = PickupCommandHandler(
                player_repo=self.deps.player_repo,
                inventory_repo=self.deps.inventory_repo,
                map_manager=self.deps.map_manager,
                broadcast_service=self.deps.broadcast_service,
                item_catalog=self.deps.item_catalog,
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._pickup_handler.message_sender = message_sender
        return self._pickup_handler

    def _get_request_stats_handler(
        self, message_sender: MessageSender
    ) -> RequestStatsCommandHandler:
        """Obtiene o crea el handler de solicitud de estadísticas.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de solicitud de estadísticas.
        """
        if self._request_stats_handler is None:
            self._request_stats_handler = RequestStatsCommandHandler(
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._request_stats_handler.message_sender = message_sender
        return self._request_stats_handler

    def _get_request_attributes_handler(
        self, message_sender: MessageSender
    ) -> RequestAttributesCommandHandler:
        """Obtiene o crea el handler de solicitud de atributos.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de solicitud de atributos.
        """
        if self._request_attributes_handler is None:
            self._request_attributes_handler = RequestAttributesCommandHandler(
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._request_attributes_handler.message_sender = message_sender
        return self._request_attributes_handler

    def _get_request_position_update_handler(
        self, message_sender: MessageSender
    ) -> RequestPositionUpdateCommandHandler:
        """Obtiene o crea el handler de solicitud de actualización de posición.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de solicitud de actualización de posición.
        """
        if self._request_position_update_handler is None:
            self._request_position_update_handler = RequestPositionUpdateCommandHandler(
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._request_position_update_handler.message_sender = message_sender
        return self._request_position_update_handler

    def _get_request_skills_handler(
        self, message_sender: MessageSender
    ) -> RequestSkillsCommandHandler:
        """Obtiene o crea el handler de solicitud de habilidades.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de solicitud de habilidades.
        """
        if self._request_skills_handler is None:
            self._request_skills_handler = RequestSkillsCommandHandler(
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._request_skills_handler.message_sender = message_sender
        return self._request_skills_handler

    def _get_spell_info_handler(self, message_sender: MessageSender) -> SpellInfoCommandHandler:
        """Obtiene o crea el handler de información de hechizos.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de información de hechizos.
        """
        if self._spell_info_handler is None:
            self._spell_info_handler = SpellInfoCommandHandler(
                spellbook_repo=self.deps.spellbook_repo,
                spell_catalog=self.deps.spell_catalog,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._spell_info_handler.message_sender = message_sender
        return self._spell_info_handler

    def _get_dice_handler(self, message_sender: MessageSender) -> DiceCommandHandler:
        """Obtiene o crea el handler de tirada de dados.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de tirada de dados.
        """
        if self._dice_handler is None:
            self._dice_handler = DiceCommandHandler(message_sender=message_sender)
        else:
            # Actualizar message_sender por si cambió
            self._dice_handler.message_sender = message_sender
        return self._dice_handler

    def _get_online_handler(self, message_sender: MessageSender) -> OnlineCommandHandler:
        """Obtiene o crea el handler de lista de jugadores online.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de lista de jugadores online.
        """
        if self._online_handler is None:
            self._online_handler = OnlineCommandHandler(
                map_manager=self.deps.map_manager,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._online_handler.message_sender = message_sender
        return self._online_handler

    def _get_information_handler(self, message_sender: MessageSender) -> InformationCommandHandler:
        """Obtiene o crea el handler de información del servidor.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de información del servidor.
        """
        if self._information_handler is None:
            self._information_handler = InformationCommandHandler(
                server_repo=self.deps.server_repo,
                map_manager=self.deps.map_manager,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._information_handler.message_sender = message_sender
        return self._information_handler

    def _get_quit_handler(self, message_sender: MessageSender) -> QuitCommandHandler:
        """Obtiene o crea el handler de desconexión.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de desconexión.
        """
        if self._quit_handler is None:
            self._quit_handler = QuitCommandHandler(
                player_repo=self.deps.player_repo,
                map_manager=self.deps.map_manager,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._quit_handler.message_sender = message_sender
        return self._quit_handler

    def _get_uptime_handler(self, message_sender: MessageSender) -> UptimeCommandHandler:
        """Obtiene o crea el handler de uptime.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de uptime.
        """
        if self._uptime_handler is None:
            self._uptime_handler = UptimeCommandHandler(
                server_repo=self.deps.server_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._uptime_handler.message_sender = message_sender
        return self._uptime_handler

    def _get_motd_handler(self, message_sender: MessageSender) -> MotdCommandHandler:
        """Obtiene o crea el handler de MOTD.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de MOTD.
        """
        if self._motd_handler is None:
            self._motd_handler = MotdCommandHandler(
                server_repo=self.deps.server_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._motd_handler.message_sender = message_sender
        return self._motd_handler

    def _get_ping_handler(self, message_sender: MessageSender) -> PingCommandHandler:
        """Obtiene o crea el handler de ping.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de ping.
        """
        if self._ping_handler is None:
            self._ping_handler = PingCommandHandler(message_sender=message_sender)
        else:
            # Actualizar message_sender por si cambió
            self._ping_handler.message_sender = message_sender
        return self._ping_handler

    def _get_ayuda_handler(self, message_sender: MessageSender) -> AyudaCommandHandler:
        """Obtiene o crea el handler de ayuda.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de ayuda.
        """
        if self._ayuda_handler is None:
            self._ayuda_handler = AyudaCommandHandler(message_sender=message_sender)
        else:
            # Actualizar message_sender por si cambió
            self._ayuda_handler.message_sender = message_sender
        return self._ayuda_handler

    def _get_commerce_end_handler(self, message_sender: MessageSender) -> CommerceEndCommandHandler:
        """Obtiene o crea el handler de cerrar comercio.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de cerrar comercio.
        """
        if self._commerce_end_handler is None:
            self._commerce_end_handler = CommerceEndCommandHandler(message_sender=message_sender)
        else:
            # Actualizar message_sender por si cambió
            self._commerce_end_handler.message_sender = message_sender
        return self._commerce_end_handler

    def _get_bank_end_handler(self, message_sender: MessageSender) -> BankEndCommandHandler:
        """Obtiene o crea el handler de cerrar banco.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de cerrar banco.
        """
        if self._bank_end_handler is None:
            self._bank_end_handler = BankEndCommandHandler(message_sender=message_sender)
        else:
            # Actualizar message_sender por si cambió
            self._bank_end_handler.message_sender = message_sender
        return self._bank_end_handler

    def _get_drop_handler(self, message_sender: MessageSender) -> DropCommandHandler:
        """Obtiene o crea el handler de soltar item.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de soltar item.
        """
        if self._drop_handler is None:
            self._drop_handler = DropCommandHandler(
                player_repo=self.deps.player_repo,
                inventory_repo=self.deps.inventory_repo,
                map_manager=self.deps.map_manager,
                broadcast_service=self.deps.broadcast_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._drop_handler.message_sender = message_sender
        return self._drop_handler

    def _get_commerce_buy_handler(self, message_sender: MessageSender) -> CommerceBuyCommandHandler:
        """Obtiene o crea el handler de comprar item.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de comprar item.
        """
        if self._commerce_buy_handler is None:
            self._commerce_buy_handler = CommerceBuyCommandHandler(
                commerce_service=self.deps.commerce_service,
                player_repo=self.deps.player_repo,
                inventory_repo=self.deps.inventory_repo,
                redis_client=self.deps.redis_client,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._commerce_buy_handler.message_sender = message_sender
        return self._commerce_buy_handler

    def _get_commerce_sell_handler(
        self, message_sender: MessageSender
    ) -> CommerceSellCommandHandler:
        """Obtiene o crea el handler de vender item.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de vender item.
        """
        if self._commerce_sell_handler is None:
            self._commerce_sell_handler = CommerceSellCommandHandler(
                commerce_service=self.deps.commerce_service,
                player_repo=self.deps.player_repo,
                inventory_repo=self.deps.inventory_repo,
                redis_client=self.deps.redis_client,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._commerce_sell_handler.message_sender = message_sender
        return self._commerce_sell_handler

    def _get_bank_deposit_handler(self, message_sender: MessageSender) -> BankDepositCommandHandler:
        """Obtiene o crea el handler de depositar item en el banco.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de depositar item en el banco.
        """
        if self._bank_deposit_handler is None:
            self._bank_deposit_handler = BankDepositCommandHandler(
                bank_repo=self.deps.bank_repo,
                inventory_repo=self.deps.inventory_repo,
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._bank_deposit_handler.message_sender = message_sender
        return self._bank_deposit_handler

    def _get_bank_extract_handler(self, message_sender: MessageSender) -> BankExtractCommandHandler:
        """Obtiene o crea el handler de extraer item del banco.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de extraer item del banco.
        """
        if self._bank_extract_handler is None:
            self._bank_extract_handler = BankExtractCommandHandler(
                bank_repo=self.deps.bank_repo,
                inventory_repo=self.deps.inventory_repo,
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._bank_extract_handler.message_sender = message_sender
        return self._bank_extract_handler

    def _get_equip_item_handler(self, message_sender: MessageSender) -> EquipItemCommandHandler:
        """Obtiene o crea el handler de equipar/desequipar item.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de equipar/desequipar item.
        """
        if self._equip_item_handler is None:
            self._equip_item_handler = EquipItemCommandHandler(
                player_repo=self.deps.player_repo,
                equipment_repo=self.deps.equipment_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._equip_item_handler.message_sender = message_sender
        return self._equip_item_handler

    def _get_work_handler(self, message_sender: MessageSender) -> WorkCommandHandler:
        """Obtiene o crea el handler de trabajo.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de trabajo.
        """
        if self._work_handler is None:
            self._work_handler = WorkCommandHandler(
                player_repo=self.deps.player_repo,
                inventory_repo=self.deps.inventory_repo,
                map_resources=self.deps.map_resources_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._work_handler.message_sender = message_sender
        return self._work_handler

    def _get_work_left_click_handler(
        self, message_sender: MessageSender
    ) -> WorkLeftClickCommandHandler:
        """Obtiene o crea el handler de trabajo con click.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de trabajo con click.
        """
        if self._work_left_click_handler is None:
            self._work_left_click_handler = WorkLeftClickCommandHandler(
                player_repo=self.deps.player_repo,
                inventory_repo=self.deps.inventory_repo,
                map_resources=self.deps.map_resources_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._work_left_click_handler.message_sender = message_sender
        return self._work_left_click_handler

    def _get_double_click_handler(self, message_sender: MessageSender) -> DoubleClickCommandHandler:
        """Obtiene o crea el handler de doble click.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de doble click.
        """
        if self._double_click_handler is None:
            self._double_click_handler = DoubleClickCommandHandler(
                player_repo=self.deps.player_repo,
                map_manager=self.deps.map_manager,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._double_click_handler.message_sender = message_sender
        return self._double_click_handler

    def _get_move_spell_handler(self, message_sender: MessageSender) -> MoveSpellCommandHandler:
        """Obtiene o crea el handler de mover hechizo.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de mover hechizo.
        """
        if self._move_spell_handler is None:
            self._move_spell_handler = MoveSpellCommandHandler(
                spellbook_repo=self.deps.spellbook_repo,
                spell_catalog=self.deps.spell_catalog,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._move_spell_handler.message_sender = message_sender
        return self._move_spell_handler

    def _get_inventory_click_handler(
        self, message_sender: MessageSender
    ) -> InventoryClickCommandHandler:
        """Obtiene o crea el handler de click en inventario.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de click en inventario.
        """
        if self._inventory_click_handler is None:
            self._inventory_click_handler = InventoryClickCommandHandler(
                player_repo=self.deps.player_repo,
                equipment_repo=self.deps.equipment_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._inventory_click_handler.message_sender = message_sender
        return self._inventory_click_handler

    def _get_left_click_handler(self, message_sender: MessageSender) -> LeftClickCommandHandler:
        """Obtiene o crea el handler de click izquierdo.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de click izquierdo.
        """
        if self._left_click_handler is None:
            self._left_click_handler = LeftClickCommandHandler(
                player_repo=self.deps.player_repo,
                map_manager=self.deps.map_manager,
                map_resources=self.deps.map_resources_service,
                bank_repo=self.deps.bank_repo,
                merchant_repo=self.deps.merchant_repo,
                door_service=self.deps.door_service,
                door_repo=self.deps.door_repo,
                redis_client=self.deps.redis_client,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._left_click_handler.message_sender = message_sender
        return self._left_click_handler

    def _get_login_handler(
        self, message_sender: MessageSender, session_data: dict[str, dict[str, int]] | None
    ) -> LoginCommandHandler:
        """Obtiene o crea el handler de login.

        Args:
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.

        Returns:
            Handler de login.
        """
        if self._login_handler is None:
            self._login_handler = LoginCommandHandler(
                player_repo=self.deps.player_repo,
                account_repo=self.deps.account_repo,
                map_manager=self.deps.map_manager,
                server_repo=self.deps.server_repo,
                spellbook_repo=self.deps.spellbook_repo,
                spell_catalog=self.deps.spell_catalog,
                equipment_repo=self.deps.equipment_repo,
                player_map_service=self.deps.player_map_service,
                message_sender=message_sender,
                session_data=session_data,
            )
        else:
            # Actualizar message_sender y session_data por si cambiaron
            self._login_handler.message_sender = message_sender
            self._login_handler.session_data = session_data or {}
        return self._login_handler

    def _get_create_account_handler(
        self, message_sender: MessageSender, session_data: dict[str, dict[str, int]] | None
    ) -> CreateAccountCommandHandler:
        """Obtiene o crea el handler de creación de cuenta.

        Args:
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.

        Returns:
            Handler de creación de cuenta.
        """
        if self._create_account_handler is None:
            self._create_account_handler = CreateAccountCommandHandler(
                player_repo=self.deps.player_repo,
                account_repo=self.deps.account_repo,
                map_manager=self.deps.map_manager,
                npc_service=self.deps.npc_service,
                server_repo=self.deps.server_repo,
                spellbook_repo=self.deps.spellbook_repo,
                spell_catalog=self.deps.spell_catalog,
                equipment_repo=self.deps.equipment_repo,
                player_map_service=self.deps.player_map_service,
                message_sender=message_sender,
                session_data=session_data,
            )
        else:
            # Actualizar message_sender y session_data por si cambiaron
            self._create_account_handler.message_sender = message_sender
            self._create_account_handler.session_data = session_data or {}
        return self._create_account_handler

    def _get_party_create_handler(self, message_sender: MessageSender) -> PartyCreateCommandHandler:
        """Obtiene o crea el handler de crear party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de crear party.
        """
        if self._party_create_handler is None:
            self._party_create_handler = PartyCreateCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_create_handler.message_sender = message_sender
        return self._party_create_handler

    def _get_party_join_handler(self, message_sender: MessageSender) -> PartyJoinCommandHandler:
        """Obtiene o crea el handler de invitar a party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de invitar a party.
        """
        if self._party_join_handler is None:
            self._party_join_handler = PartyJoinCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_join_handler.message_sender = message_sender
        return self._party_join_handler

    def _get_party_accept_handler(self, message_sender: MessageSender) -> PartyAcceptCommandHandler:
        """Obtiene o crea el handler de aceptar invitación a party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de aceptar invitación.
        """
        if self._party_accept_handler is None:
            self._party_accept_handler = PartyAcceptCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_accept_handler.message_sender = message_sender
        return self._party_accept_handler

    def _get_party_leave_handler(self, message_sender: MessageSender) -> PartyLeaveCommandHandler:
        """Obtiene o crea el handler de abandonar party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de abandonar party.
        """
        if self._party_leave_handler is None:
            self._party_leave_handler = PartyLeaveCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_leave_handler.message_sender = message_sender
        return self._party_leave_handler

    def _get_party_message_handler(
        self, message_sender: MessageSender
    ) -> PartyMessageCommandHandler:
        """Obtiene o crea el handler de enviar mensaje a party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de enviar mensaje a party.
        """
        if self._party_message_handler is None:
            self._party_message_handler = PartyMessageCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_message_handler.message_sender = message_sender
        return self._party_message_handler

    def _get_party_kick_handler(self, message_sender: MessageSender) -> PartyKickCommandHandler:
        """Obtiene o crea el handler de expulsar miembro de party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de expulsar miembro.
        """
        if self._party_kick_handler is None:
            self._party_kick_handler = PartyKickCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_kick_handler.message_sender = message_sender
        return self._party_kick_handler

    def _get_party_set_leader_handler(
        self, message_sender: MessageSender
    ) -> PartySetLeaderCommandHandler:
        """Obtiene o crea el handler de transferir liderazgo de party.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de transferir liderazgo.
        """
        if self._party_set_leader_handler is None:
            self._party_set_leader_handler = PartySetLeaderCommandHandler(
                party_service=self.deps.party_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._party_set_leader_handler.message_sender = message_sender
        return self._party_set_leader_handler

    def _get_talk_handler(
        self, message_sender: MessageSender, session_data: dict[str, dict[str, int]] | None
    ) -> TalkCommandHandler:
        """Obtiene o crea el handler de mensaje de chat.

        Args:
            message_sender: Enviador de mensajes.
            session_data: Datos de sesión compartidos.

        Returns:
            Handler de mensaje de chat.
        """
        if self._talk_handler is None:
            self._talk_handler = TalkCommandHandler(
                player_repo=self.deps.player_repo,
                account_repo=self.deps.account_repo,
                map_manager=self.deps.map_manager,
                game_tick=self.deps.game_tick,
                message_sender=message_sender,
                clan_service=self.deps.clan_service,
                session_data=session_data,
            )
        else:
            # Actualizar message_sender y session_data por si cambiaron
            self._talk_handler.message_sender = message_sender
            self._talk_handler.session_data = session_data or {}
        return self._talk_handler

    def _get_gm_command_handler(self, message_sender: MessageSender) -> GMCommandHandler:
        """Obtiene o crea el handler de comandos de Game Master.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de comandos de Game Master.
        """
        if self._gm_command_handler is None:
            self._gm_command_handler = GMCommandHandler(
                player_repo=self.deps.player_repo,
                player_map_service=self.deps.player_map_service,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._gm_command_handler.message_sender = message_sender
        return self._gm_command_handler

    def _get_bank_deposit_gold_handler(
        self, message_sender: MessageSender
    ) -> BankDepositGoldCommandHandler:
        """Obtiene o crea el handler de depositar oro en el banco.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de depositar oro en el banco.
        """
        if self._bank_deposit_gold_handler is None:
            self._bank_deposit_gold_handler = BankDepositGoldCommandHandler(
                bank_repo=self.deps.bank_repo,
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._bank_deposit_gold_handler.message_sender = message_sender
        return self._bank_deposit_gold_handler

    def _get_bank_extract_gold_handler(
        self, message_sender: MessageSender
    ) -> BankExtractGoldCommandHandler:
        """Obtiene o crea el handler de extraer oro del banco.

        Args:
            message_sender: Enviador de mensajes.

        Returns:
            Handler de extraer oro del banco.
        """
        if self._bank_extract_gold_handler is None:
            self._bank_extract_gold_handler = BankExtractGoldCommandHandler(
                bank_repo=self.deps.bank_repo,
                player_repo=self.deps.player_repo,
                message_sender=message_sender,
            )
        else:
            # Actualizar message_sender por si cambió
            self._bank_extract_gold_handler.message_sender = message_sender
        return self._bank_extract_gold_handler

    def create_task(
        self,
        data: bytes,
        message_sender: MessageSender,
        session_data: dict[str, Any],
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
                    commerce_sell_handler=self._get_commerce_sell_handler(message_sender),
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
                    commerce_buy_handler=self._get_commerce_buy_handler(message_sender),
                    session_data=session_data,
                )

            # TaskInventoryClick (packet_id 23) - recibe slot
            if task_class == TaskInventoryClick and "slot" in parsed_data:
                return TaskInventoryClick(
                    data,
                    message_sender,
                    slot=parsed_data["slot"],
                    inventory_click_handler=self._get_inventory_click_handler(message_sender),
                    session_data=session_data,
                )

            # TaskUseItem (packet_id 30) - recibe slot
            if task_class == TaskUseItem and "slot" in parsed_data:
                return TaskUseItem(
                    data=data,
                    message_sender=message_sender,
                    slot=parsed_data["slot"],
                    use_item_handler=self._get_use_item_handler(message_sender),
                    session_data=session_data,
                )

            # TaskMoveSpell (packet_id 45) - recibe slot y upwards
            if task_class == TaskMoveSpell and "slot" in parsed_data and "upwards" in parsed_data:
                return TaskMoveSpell(
                    data=data,
                    message_sender=message_sender,
                    move_spell_handler=self._get_move_spell_handler(message_sender),
                    session_data=session_data,
                )

            # TaskSpellInfo (packet_id 35) - recibe slot
            if task_class == TaskSpellInfo and "slot" in parsed_data:
                return TaskSpellInfo(
                    data=data,
                    message_sender=message_sender,
                    spell_info_handler=self._get_spell_info_handler(message_sender),
                    session_data=session_data,
                    slot=parsed_data["slot"],
                )

            # TaskBankExtractGold (packet_id 111) - recibe amount
            if task_class == TaskBankExtractGold and "amount" in parsed_data:
                return TaskBankExtractGold(
                    data=data,
                    message_sender=message_sender,
                    amount=parsed_data["amount"],
                    bank_extract_gold_handler=self._get_bank_extract_gold_handler(message_sender),
                    session_data=session_data,
                )

            # TaskBankDepositGold (packet_id 112) - recibe amount
            if task_class == TaskBankDepositGold and "amount" in parsed_data:
                return TaskBankDepositGold(
                    data=data,
                    message_sender=message_sender,
                    amount=parsed_data["amount"],
                    bank_deposit_gold_handler=self._get_bank_deposit_gold_handler(message_sender),
                    session_data=session_data,
                )

        # Mapeo de task_class a función constructora con dependencias
        task_factories: dict[type, Callable[[], Task]] = {
            TaskLogin: lambda: TaskLogin(
                data,
                message_sender,
                login_handler=self._get_login_handler(message_sender, session_data),
                session_data=session_data,
            ),
            TaskCreateAccount: lambda: TaskCreateAccount(
                data,
                message_sender,
                create_account_handler=self._get_create_account_handler(
                    message_sender, session_data
                ),
                session_data=session_data,
            ),
            TaskDice: lambda: TaskDice(
                data,
                message_sender,
                dice_handler=self._get_dice_handler(message_sender),
                session_data=session_data,
                server_repo=self.deps.server_repo,
            ),
            TaskRequestAttributes: lambda: TaskRequestAttributes(
                data,
                message_sender,
                request_attributes_handler=self._get_request_attributes_handler(message_sender),
                session_data=session_data,
            ),
            TaskRequestSkills: lambda: TaskRequestSkills(
                data,
                message_sender,
                request_skills_handler=self._get_request_skills_handler(message_sender),
                session_data=session_data,
            ),
            TaskTalk: lambda: TaskTalk(
                data,
                message_sender,
                talk_handler=self._get_talk_handler(message_sender, session_data),
                session_data=session_data,
            ),
            TaskWalk: lambda: TaskWalk(
                data,
                message_sender,
                self._get_walk_handler(message_sender),
                session_data,
            ),
            TaskGMCommands: lambda: TaskGMCommands(
                data,
                message_sender,
                gm_command_handler=self._get_gm_command_handler(message_sender),
                session_data=session_data,
            ),
            TaskChangeHeading: lambda: TaskChangeHeading(
                data,
                message_sender,
                change_heading_handler=self._get_change_heading_handler(
                    message_sender, session_data
                ),
                session_data=session_data,
            ),
            TaskMeditate: lambda: TaskMeditate(
                data,
                message_sender,
                meditate_handler=self._get_meditate_handler(message_sender),
                session_data=session_data,
            ),
            TaskRequestStats: lambda: TaskRequestStats(
                data,
                message_sender,
                request_stats_handler=self._get_request_stats_handler(message_sender),
                session_data=session_data,
            ),
            TaskRequestPositionUpdate: lambda: TaskRequestPositionUpdate(
                data,
                message_sender,
                request_position_update_handler=self._get_request_position_update_handler(
                    message_sender
                ),
                session_data=session_data,
            ),
            TaskOnline: lambda: TaskOnline(
                data,
                message_sender,
                online_handler=self._get_online_handler(message_sender),
                session_data=session_data,
            ),
            TaskMotd: lambda: TaskMotd(
                data,
                message_sender,
                motd_handler=self._get_motd_handler(message_sender),
            ),
            TaskInformation: lambda: TaskInformation(
                data,
                message_sender,
                information_handler=self._get_information_handler(message_sender),
            ),
            TaskUptime: lambda: TaskUptime(
                data,
                message_sender,
                uptime_handler=self._get_uptime_handler(message_sender),
            ),
            TaskQuit: lambda: TaskQuit(
                data,
                message_sender,
                quit_handler=self._get_quit_handler(message_sender),
                session_data=session_data,
            ),
            TaskDoubleClick: lambda: TaskDoubleClick(
                data,
                message_sender,
                double_click_handler=self._get_double_click_handler(message_sender),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskLeftClick: lambda: TaskLeftClick(
                data,
                message_sender,
                left_click_handler=self._get_left_click_handler(message_sender),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            # TaskInventoryClick: manejada arriba con datos validados
            TaskEquipItem: lambda: TaskEquipItem(
                data,
                message_sender,
                equip_item_handler=self._get_equip_item_handler(message_sender),
                session_data=session_data,
            ),
            TaskAttack: lambda: TaskAttack(
                data,
                message_sender,
                attack_handler=self._get_attack_handler(message_sender),
                session_data=session_data,
            ),
            TaskPickup: lambda: TaskPickup(
                data,
                message_sender,
                pickup_handler=self._get_pickup_handler(message_sender),
                session_data=session_data,
            ),
            TaskDrop: lambda: TaskDrop(
                data,
                message_sender,
                drop_handler=self._get_drop_handler(message_sender),
                session_data=session_data,
            ),
            # TaskCommerceBuy: manejada arriba con datos validados
            # TaskCommerceSell: manejada arriba con datos validados
            TaskBankDeposit: lambda: TaskBankDeposit(
                data,
                message_sender,
                bank_deposit_handler=self._get_bank_deposit_handler(message_sender),
                session_data=session_data,
            ),
            TaskBankExtract: lambda: TaskBankExtract(
                data,
                message_sender,
                bank_extract_handler=self._get_bank_extract_handler(message_sender),
                session_data=session_data,
            ),
            TaskBankEnd: lambda: TaskBankEnd(
                data,
                message_sender,
                bank_end_handler=self._get_bank_end_handler(message_sender),
                session_data=session_data,
            ),
            TaskCommerceEnd: lambda: TaskCommerceEnd(
                data,
                message_sender,
                commerce_end_handler=self._get_commerce_end_handler(message_sender),
            ),
            TaskAyuda: lambda: TaskAyuda(
                data,
                message_sender,
                ayuda_handler=self._get_ayuda_handler(message_sender),
            ),
            TaskPing: lambda: TaskPing(
                data,
                message_sender,
                ping_handler=self._get_ping_handler(message_sender),
            ),
            TaskPartyCreate: lambda: TaskPartyCreate(
                data,
                message_sender,
                party_create_handler=self._get_party_create_handler(message_sender),
                session_data=session_data,
            ),
            TaskPartyJoin: lambda: TaskPartyJoin(
                data,
                message_sender,
                party_join_handler=self._get_party_join_handler(message_sender),
                session_data=session_data,
            ),
            TaskPartyAcceptMember: lambda: TaskPartyAcceptMember(
                data,
                message_sender,
                party_accept_handler=self._get_party_accept_handler(message_sender),
                session_data=session_data,
            ),
            TaskPartyLeave: lambda: TaskPartyLeave(
                data,
                message_sender,
                party_leave_handler=self._get_party_leave_handler(message_sender),
                session_data=session_data,
            ),
            TaskPartyMessage: lambda: TaskPartyMessage(
                data,
                message_sender,
                party_message_handler=self._get_party_message_handler(message_sender),
                session_data=session_data,
            ),
            TaskPartyKick: lambda: TaskPartyKick(
                data,
                message_sender,
                party_kick_handler=self._get_party_kick_handler(message_sender),
                session_data=session_data,
            ),
            TaskPartySetLeader: lambda: TaskPartySetLeader(
                data,
                message_sender,
                party_set_leader_handler=self._get_party_set_leader_handler(message_sender),
                session_data=session_data,
            ),
            TaskWork: lambda: TaskWork(
                data,
                message_sender,
                work_handler=self._get_work_handler(message_sender),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskWorkLeftClick: lambda: TaskWorkLeftClick(
                data,
                message_sender,
                work_left_click_handler=self._get_work_left_click_handler(message_sender),
                player_repo=self.deps.player_repo,
                session_data=session_data,
            ),
            TaskMoveSpell: lambda: TaskMoveSpell(
                data,
                message_sender,
                move_spell_handler=self._get_move_spell_handler(message_sender),
                session_data=session_data,
            ),
            TaskSpellInfo: lambda: TaskSpellInfo(
                data,
                message_sender,
                spell_info_handler=self._get_spell_info_handler(message_sender),
                session_data=session_data,
            ),
            TaskCastSpell: lambda: TaskCastSpell(
                data,
                message_sender,
                self._get_cast_spell_handler(message_sender),
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
