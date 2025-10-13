"""Sistema de tareas para procesar mensajes del cliente."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.message_sender import MessageSender


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
