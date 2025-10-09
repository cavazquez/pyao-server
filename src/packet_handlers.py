"""Mapeo de IDs de paquetes a sus handlers correspondientes."""

from src.packet_id import ClientPacketID
from src.task import Task, TaskDice

# Mapeo de PacketID a clase de Task
TASK_HANDLERS: dict[int, type[Task]] = {
    ClientPacketID.THROW_DICES: TaskDice,
}
