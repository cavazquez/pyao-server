"""Tests para la clase base TickEffect."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock

import pytest

from src.tick_effect import TickEffect

if TYPE_CHECKING:
    from src.message_sender import MessageSender
    from src.player_repository import PlayerRepository


class ConcreteTickEffect(TickEffect):
    """Implementación concreta de TickEffect para testing."""

    def __init__(self, interval: float = 1.0, name: str = "TestEffect") -> None:
        """Inicializa el efecto de prueba.

        Args:
            interval: Intervalo en segundos.
            name: Nombre del efecto.
        """
        self.interval = interval
        self.name = name
        self.apply_called = False

    async def apply(
        self,
        user_id: int,  # noqa: ARG002
        player_repo: PlayerRepository,  # noqa: ARG002
        message_sender: MessageSender | None,  # noqa: ARG002
    ) -> None:
        """Implementación de apply para testing."""
        self.apply_called = True

    def get_interval_seconds(self) -> float:
        """Retorna el intervalo configurado.

        Returns:
            Intervalo en segundos.
        """
        return self.interval

    def get_name(self) -> str:
        """Retorna el nombre configurado.

        Returns:
            Nombre del efecto.
        """
        return self.name


def test_tick_effect_abstract_methods() -> None:
    """Test que verifica que TickEffect es abstracta y requiere implementación."""
    # Intentar instanciar TickEffect directamente debe fallar
    with pytest.raises(TypeError):
        TickEffect()  # type: ignore[abstract]


@pytest.mark.asyncio
async def test_concrete_tick_effect_apply() -> None:
    """Test que verifica que una implementación concreta puede aplicar el efecto."""
    effect = ConcreteTickEffect(interval=5.0, name="CustomEffect")
    mock_player_repo = AsyncMock()
    mock_message_sender = AsyncMock()

    # Aplicar el efecto
    await effect.apply(user_id=1, player_repo=mock_player_repo, message_sender=mock_message_sender)

    # Verificar que se llamó
    assert effect.apply_called is True


def test_concrete_tick_effect_get_interval() -> None:
    """Test que verifica que get_interval_seconds retorna el valor correcto."""
    effect = ConcreteTickEffect(interval=10.0)
    assert effect.get_interval_seconds() == 10.0


def test_concrete_tick_effect_get_name() -> None:
    """Test que verifica que get_name retorna el nombre correcto."""
    effect = ConcreteTickEffect(name="MyEffect")
    assert effect.get_name() == "MyEffect"


@pytest.mark.asyncio
async def test_tick_effect_with_none_message_sender() -> None:
    """Test que verifica que el efecto puede manejar message_sender None."""
    effect = ConcreteTickEffect()
    mock_player_repo = AsyncMock()

    # Aplicar el efecto sin message_sender
    await effect.apply(user_id=1, player_repo=mock_player_repo, message_sender=None)

    # Verificar que se llamó sin errores
    assert effect.apply_called is True
