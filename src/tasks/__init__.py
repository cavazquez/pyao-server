"""Package de tasks del servidor.

Este módulo exporta la clase base Task.

Para TaskFactory, usa importación directa:
    from src.tasks.task_factory import TaskFactory

Ejemplo de uso:
    from src.tasks import Task
"""

from src.tasks.task import Task

__all__ = [
    "Task",
]
