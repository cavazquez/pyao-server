"""Mapeo de IDs de paquetes a sus handlers correspondientes."""

from typing import TYPE_CHECKING

from src.packet_id import ClientPacketID
from src.task_account import TaskCreateAccount
from src.task_attributes import TaskRequestAttributes
from src.task_ayuda import TaskAyuda
from src.task_bank_end import TaskBankEnd
from src.task_cast_spell import TaskCastSpell
from src.task_change_heading import TaskChangeHeading
from src.task_commerce_end import TaskCommerceEnd
from src.task_dice import TaskDice
from src.task_double_click import TaskDoubleClick
from src.task_equip_item import TaskEquipItem
from src.task_information import TaskInformation
from src.task_inventory_click import TaskInventoryClick
from src.task_left_click import TaskLeftClick
from src.task_login import TaskLogin
from src.task_meditate import TaskMeditate
from src.task_motd import TaskMotd
from src.task_online import TaskOnline
from src.task_ping import TaskPing
from src.task_quit import TaskQuit
from src.task_request_stats import TaskRequestStats
from src.task_talk import TaskTalk
from src.task_uptime import TaskUptime
from src.task_walk import TaskWalk

if TYPE_CHECKING:
    from src.task import Task

# Mapeo de PacketID a clase de Task
TASK_HANDLERS: dict[int, type[Task]] = {
    ClientPacketID.LOGIN: TaskLogin,
    ClientPacketID.THROW_DICES: TaskDice,
    ClientPacketID.CREATE_ACCOUNT: TaskCreateAccount,
    ClientPacketID.TALK: TaskTalk,
    ClientPacketID.WALK: TaskWalk,
    ClientPacketID.CAST_SPELL: TaskCastSpell,  # Lanzar hechizo
    ClientPacketID.LEFT_CLICK: TaskLeftClick,  # Click en personaje/NPC
    ClientPacketID.DOUBLE_CLICK: TaskDoubleClick,  # Doble click - item o NPC
    ClientPacketID.USE_ITEM: TaskInventoryClick,  # Click en inventario - mostrar info
    ClientPacketID.EQUIP_ITEM: TaskEquipItem,  # Equipar/desequipar item
    ClientPacketID.CHANGE_HEADING: TaskChangeHeading,
    ClientPacketID.REQUEST_ATTRIBUTES: TaskRequestAttributes,
    ClientPacketID.COMMERCE_END: TaskCommerceEnd,  # Cerrar ventana de comercio
    ClientPacketID.BANK_END: TaskBankEnd,  # Cerrar ventana de banco
    ClientPacketID.AYUDA: TaskAyuda,
    ClientPacketID.MEDITATE: TaskMeditate,  # Meditar
    ClientPacketID.REQUEST_STATS: TaskRequestStats,
    ClientPacketID.INFORMATION: TaskInformation,
    ClientPacketID.REQUEST_MOTD: TaskMotd,
    ClientPacketID.UPTIME: TaskUptime,
    ClientPacketID.ONLINE: TaskOnline,
    ClientPacketID.QUIT: TaskQuit,
    ClientPacketID.PING: TaskPing,
}
