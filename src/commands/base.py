"""Clases base para el Command Pattern."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Command:
    """Clase base para comandos (solo datos)."""


@dataclass
class CommandResult:
    """Resultado de ejecutar un comando.

    Attributes:
        success: Si el comando se ejecutó exitosamente.
        error_message: Mensaje de error si success es False.
        data: Datos adicionales del resultado.
    """

    success: bool
    error_message: str | None = None
    data: dict[str, Any] | None = None

    @classmethod
    def ok(cls, data: dict[str, Any] | None = None) -> CommandResult:
        """Crea un resultado exitoso.

        Args:
            data: Datos adicionales del resultado.

        Returns:
            CommandResult con success=True.
        """
        return cls(success=True, data=data)

    @classmethod
    def error(cls, message: str) -> CommandResult:
        """Crea un resultado con error.

        Args:
            message: Mensaje de error.

        Returns:
            CommandResult con success=False.
        """
        return cls(success=False, error_message=message)


class CommandHandler(ABC):
    """Clase base para handlers de comandos (solo lógica de negocio)."""

    @abstractmethod
    async def handle(self, command: Command) -> CommandResult:
        """Ejecuta el comando.

        Args:
            command: Comando a ejecutar.

        Returns:
            Resultado de la ejecución.
        """
        raise NotImplementedError
