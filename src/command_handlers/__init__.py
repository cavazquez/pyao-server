"""Handlers de comandos usando Command Pattern."""

from src.command_handlers.attack_handler import AttackCommandHandler
from src.command_handlers.bank_deposit_gold_handler import BankDepositGoldCommandHandler
from src.command_handlers.bank_deposit_handler import BankDepositCommandHandler
from src.command_handlers.bank_extract_gold_handler import BankExtractGoldCommandHandler
from src.command_handlers.bank_extract_handler import BankExtractCommandHandler
from src.command_handlers.cast_spell_handler import CastSpellCommandHandler
from src.command_handlers.commerce_buy_handler import CommerceBuyCommandHandler
from src.command_handlers.commerce_sell_handler import CommerceSellCommandHandler
from src.command_handlers.drop_handler import DropCommandHandler
from src.command_handlers.equip_item_handler import EquipItemCommandHandler
from src.command_handlers.pickup_handler import PickupCommandHandler
from src.command_handlers.use_item_handler import UseItemCommandHandler
from src.command_handlers.walk_handler import WalkCommandHandler
from src.command_handlers.work_handler import WorkCommandHandler

__all__ = [
    "AttackCommandHandler",
    "BankDepositCommandHandler",
    "BankDepositGoldCommandHandler",
    "BankExtractCommandHandler",
    "BankExtractGoldCommandHandler",
    "CastSpellCommandHandler",
    "CommerceBuyCommandHandler",
    "CommerceSellCommandHandler",
    "DropCommandHandler",
    "EquipItemCommandHandler",
    "PickupCommandHandler",
    "UseItemCommandHandler",
    "WalkCommandHandler",
    "WorkCommandHandler",
]
