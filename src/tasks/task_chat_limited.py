"""Descarta conversación limitada sin generar otro flood de respuestas."""

from typing import TYPE_CHECKING

from src.tasks.task import Task

if TYPE_CHECKING:
    from src.messaging.message_sender import MessageSender


class TaskChatLimited(Task):
    """No delega al handler ni realiza consultas de mundo, cuenta o grupo."""

    def __init__(self, data: bytes, message_sender: MessageSender, *, notify: bool) -> None:
        """Conserva sólo si corresponde enviar el aviso de esta ventana."""
        super().__init__(data, message_sender)
        self.notify = notify

    async def execute(self) -> None:
        """Responde como máximo una vez por cinco segundos y usuario."""
        if self.notify:
            await self.message_sender.send_console_msg(
                "Límite de mensajes alcanzado; esperá un momento o acortá el texto."
            )
