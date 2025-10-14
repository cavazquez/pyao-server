"""Mapeo de IDs de paquetes a sus handlers correspondientes."""

from typing import TYPE_CHECKING

from src.packet_id import ClientPacketID
from src.task_account import TaskCreateAccount
from src.task_attributes import TaskRequestAttributes
from src.task_ayuda import TaskAyuda
from src.task_change_heading import TaskChangeHeading
from src.task_dice import TaskDice
from src.task_information import TaskInformation
from src.task_inventory_click import TaskInventoryClick
from src.task_login import TaskLogin
from src.task_motd import TaskMotd
from src.task_online import TaskOnline
from src.task_ping import TaskPing
from src.task_quit import TaskQuit
from src.task_request_stats import TaskRequestStats
from src.task_talk import TaskTalk
from src.task_uptime import TaskUptime
from src.task_use_item import TaskUseItem
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
    ClientPacketID.DOUBLE_CLICK: TaskUseItem,  # Doble click - usar item
    ClientPacketID.USE_ITEM: TaskInventoryClick,  # Click en inventario - mostrar info
    ClientPacketID.CHANGE_HEADING: TaskChangeHeading,
    ClientPacketID.REQUEST_ATTRIBUTES: TaskRequestAttributes,
    ClientPacketID.AYUDA: TaskAyuda,
    ClientPacketID.REQUEST_STATS: TaskRequestStats,
    ClientPacketID.INFORMATION: TaskInformation,
    ClientPacketID.REQUEST_MOTD: TaskMotd,
    ClientPacketID.UPTIME: TaskUptime,
    ClientPacketID.ONLINE: TaskOnline,
    ClientPacketID.QUIT: TaskQuit,
    ClientPacketID.PING: TaskPing,
}
