"""Sistema de tareas para procesar mensajes del cliente."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.message_sender import MessageSender

# Constantes compartidas
MIN_USERNAME_LENGTH = 3
MIN_PASSWORD_LENGTH = 6
MIN_TALK_PACKET_SIZE = 3  # PacketID + int16


class Task(ABC):
    """Clase base para tareas que procesan mensajes del cliente."""

    def __init__(self, data: bytes, message_sender: MessageSender) -> None:
        """Inicializa la tarea.

        Args:
            data: Datos recibidos del cliente.
            message_sender: Enviador de mensajes para comunicarse con el cliente.
        """
        self.data = data
        self.message_sender = message_sender

    @abstractmethod
    async def execute(self) -> None:
        """Ejecuta la tarea. Debe ser implementado por las subclases."""
        ...


# Re-exportar todas las clases de tareas desde sus módulos
from src.task_account import TaskCreateAccount  # noqa: E402
from src.task_attributes import TaskRequestAttributes  # noqa: E402
from src.task_dice import TaskDice  # noqa: E402
from src.task_login import TaskLogin  # noqa: E402
from src.task_null import TaskNull  # noqa: E402
from src.task_talk import TaskTalk  # noqa: E402

__all__ = [
    "MIN_PASSWORD_LENGTH",
    "MIN_TALK_PACKET_SIZE",
    "MIN_USERNAME_LENGTH",
    "Task",
    "TaskCreateAccount",
    "TaskDice",
    "TaskLogin",
    "TaskNull",
    "TaskRequestAttributes",
    "TaskTalk",
]
