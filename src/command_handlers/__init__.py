"""Handlers de comandos usando Command Pattern.

Este módulo exporta todos los handlers de comandos usando Command Pattern.

Las importaciones aquí permiten importar handlers directamente desde el paquete:

    from src.command_handlers import AttackCommandHandler

Aunque actualmente el código usa importaciones directas desde módulos:

    from src.command_handlers.attack_handler import AttackCommandHandler

Ambas formas funcionan. Las importaciones aquí facilitan el uso futuro del paquete.
"""

from src.command_handlers.attack_handler import AttackCommandHandler
from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
from src.command_handlers.bank_deposit_handler import BankDepositCommandHandler
from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
from src.command_handlers.commerce_buy_handler import CommerceBuyCommandHandler
from src.command_handlers.commerce_sell_handler import CommerceSellCommandHandler
from src.command_handlers.create_account_handler import CreateAccountCommandHandler
from src.command_handlers.double_click_handler import DoubleClickCommandHandler
from src.command_handlers.drop_handler import DropCommandHandler
from src.command_handlers.equip_item_handler import EquipItemCommandHandler
from src.command_handlers.gm_command_handler import GMCommandHandler
from src.command_handlers.inventory_click_handler import InventoryClickCommandHandler
from src.command_handlers.left_click_handler import LeftClickCommandHandler
from src.command_handlers.login_handler import LoginCommandHandler
from src.command_handlers.move_spell_handler import MoveSpellCommandHandler
from src.command_handlers.party_accept_handler import PartyAcceptCommandHandler
from src.command_handlers.party_create_handler import PartyCreateCommandHandler
from src.command_handlers.party_join_handler import PartyJoinCommandHandler
from src.command_handlers.party_kick_handler import PartyKickCommandHandler
from src.command_handlers.party_leave_handler import PartyLeaveCommandHandler
from src.command_handlers.party_message_handler import PartyMessageCommandHandler
from src.command_handlers.party_set_leader_handler import PartySetLeaderCommandHandler
from src.command_handlers.pickup_handler import PickupCommandHandler
from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.command_handlers.walk_handler import WalkCommandHandler
from src.command_handlers.work_handler import WorkCommandHandler
from src.command_handlers.work_left_click_handler import WorkLeftClickCommandHandler

__all__ = [
    "AttackCommandHandler",
    "BankDepositCommandHandler",
    "BankDepositGoldCommandHandler",
    "BankExtractCommandHandler",
    "BankExtractGoldCommandHandler",
    "CastSpellCommandHandler",
    "CommerceBuyCommandHandler",
    "CommerceSellCommandHandler",
    "CreateAccountCommandHandler",
    "DoubleClickCommandHandler",
    "DropCommandHandler",
    "EquipItemCommandHandler",
    "GMCommandHandler",
    "InventoryClickCommandHandler",
    "LeftClickCommandHandler",
    "LoginCommandHandler",
    "MoveSpellCommandHandler",
    "PartyAcceptCommandHandler",
    "PartyCreateCommandHandler",
    "PartyJoinCommandHandler",
    "PartyKickCommandHandler",
    "PartyLeaveCommandHandler",
    "PartyMessageCommandHandler",
    "PartySetLeaderCommandHandler",
    "PickupCommandHandler",
    "UseItemCommandHandler",
    "WalkCommandHandler",
    "WorkCommandHandler",
    "WorkLeftClickCommandHandler",
]
