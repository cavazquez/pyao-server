"""Mapeo de IDs de paquetes a sus handlers correspondientes."""

from src.packet_id import ClientPacketID
from src.task import Task, TaskCreateAccount, TaskDice, TaskLogin, TaskRequestAttributes, TaskTalk
from src.task_walk import TaskWalk

# Mapeo de PacketID a clase de Task
TASK_HANDLERS: dict[int, type[Task]] = {
    ClientPacketID.LOGIN: TaskLogin,
    ClientPacketID.THROW_DICES: TaskDice,
    ClientPacketID.CREATE_ACCOUNT: TaskCreateAccount,
    ClientPacketID.TALK: TaskTalk,
    ClientPacketID.WALK: TaskWalk,
    ClientPacketID.REQUEST_ATTRIBUTES: TaskRequestAttributes,
}
