"""Negociación optativa por conexión: nunca agrega mensajes al login legacy."""

from dataclasses import dataclass, field
from enum import IntFlag
from time import monotonic
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

CAPABILITIES_VERSION = 1
NEGOTIATION_WINDOW_SECONDS = 10.0


class Capability(IntFlag):
    """Bits estables; declarar un bit no significa implementar la función."""

    NONE = 0
    SKILLS_CATALOG = 1
    TARGETED_CAST = 2
    SKILL_ALLOCATION = 4
    PASSWORD_CHANGE = 8
    VISUAL_DAMAGE = 16
    PROJECTILES = 32
    WEATHER = 64
    TRADE_STATE = 128
    SKILL_ACTIONS = 256


# Se habilitan sólo al integrar la implementación y sus pruebas de cada feature.
SUPPORTED_CAPABILITIES = (
    Capability.SKILLS_CATALOG
    | Capability.TRADE_STATE
    | Capability.SKILL_ALLOCATION
    | Capability.PASSWORD_CHANGE
    | Capability.TARGETED_CAST
    | Capability.SKILL_ACTIONS
)


@dataclass
class ConnectionCapabilities:
    """Estado exclusivo de una sesión, con presupuesto temporal después de autenticar."""

    supported: Capability = SUPPORTED_CAPABILITIES
    clock: Callable[[], float] = monotonic
    enabled: Capability = field(default=Capability.NONE, init=False)
    negotiated: bool = field(default=False, init=False)
    deadline: float | None = field(default=None, init=False)

    def after_login(self) -> None:
        """Abre una ventana sin emitir un solo byte al cliente legacy."""
        self.clear()
        self.deadline = self.clock() + NEGOTIATION_WINDOW_SECONDS

    def clear(self) -> None:
        """El cierre y la reconexión no heredan capacidades."""
        self.enabled = Capability.NONE
        self.negotiated = False
        self.deadline = None

    def negotiate(self, version: int, requested: int) -> int | None:
        """Acepta sólo una intersección válida dentro de la ventana autenticada.

        Returns:
            Máscara a responder, o None si se ignora un pedido inválido o tardío.
        """
        if (
            self.deadline is None
            or self.clock() > self.deadline
            or version != CAPABILITIES_VERSION
            or requested < 0
        ):
            return None
        if not self.negotiated:
            self.enabled = Capability(requested) & self.supported
            self.negotiated = True
        return int(self.enabled)
