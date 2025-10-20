"""Tests para StaminaService."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.stamina_service import (
    STAMINA_COST_ATTACK,
    STAMINA_COST_SPELL,
    STAMINA_COST_WALK,
    STAMINA_COST_WORK,
    STAMINA_REGEN_RATE,
    STAMINA_REGEN_RESTING,
    StaminaService,
)


@pytest.mark.asyncio
class TestStaminaService:
    """Tests para StaminaService."""

    async def test_consume_stamina_success(self) -> None:
        """Test de consumo exitoso de stamina."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(100, 100))
        player_repo.update_stamina = AsyncMock()

        # Mock del message_sender
        message_sender = MagicMock()
        message_sender.send_update_sta = AsyncMock()

        service = StaminaService(player_repo)

        # Consumir stamina
        result = await service.consume_stamina(1, 10, message_sender)

        assert result is True
        player_repo.update_stamina.assert_called_once_with(1, 90)
        message_sender.send_update_sta.assert_called_once_with(90)

    async def test_consume_stamina_insufficient(self) -> None:
        """Test de consumo con stamina insuficiente."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(5, 100))

        # Mock del message_sender
        message_sender = MagicMock()
        message_sender.send_console_msg = AsyncMock()

        service = StaminaService(player_repo)

        # Intentar consumir más stamina de la disponible
        result = await service.consume_stamina(1, 10, message_sender)

        assert result is False
        message_sender.send_console_msg.assert_called_once_with("No tienes suficiente energía.")

    async def test_consume_stamina_without_message_sender(self) -> None:
        """Test de consumo sin message_sender."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(50, 100))
        player_repo.update_stamina = AsyncMock()

        service = StaminaService(player_repo)

        # Consumir stamina sin message_sender
        result = await service.consume_stamina(1, 20)

        assert result is True
        player_repo.update_stamina.assert_called_once_with(1, 30)

    async def test_consume_stamina_to_zero(self) -> None:
        """Test de consumo que lleva stamina a 0."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(10, 100))
        player_repo.update_stamina = AsyncMock()

        service = StaminaService(player_repo)

        # Consumir exactamente toda la stamina
        result = await service.consume_stamina(1, 10)

        assert result is True
        # Debe quedar en 0
        player_repo.update_stamina.assert_called_once_with(1, 0)

    async def test_can_perform_action_sufficient_stamina(self) -> None:
        """Test de verificación con stamina suficiente."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(50, 100))

        service = StaminaService(player_repo)

        # Verificar acción con costo de 10
        result = await service.can_perform_action(1, 10)

        assert result is True

    async def test_can_perform_action_insufficient_stamina(self) -> None:
        """Test de verificación con stamina insuficiente."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(5, 100))

        service = StaminaService(player_repo)

        # Verificar acción con costo de 10
        result = await service.can_perform_action(1, 10)

        assert result is False

    async def test_can_perform_action_exact_stamina(self) -> None:
        """Test de verificación con stamina exacta."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(10, 100))

        service = StaminaService(player_repo)

        # Verificar acción con costo exacto
        result = await service.can_perform_action(1, 10)

        assert result is True

    async def test_regenerate_stamina_normal(self) -> None:
        """Test de regeneración normal de stamina."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(50, 100))
        player_repo.update_stamina = AsyncMock()

        # Mock del message_sender
        message_sender = MagicMock()
        message_sender.send_update_sta = AsyncMock()

        service = StaminaService(player_repo)

        # Regenerar stamina
        await service.regenerate_stamina(1, 10, message_sender)

        player_repo.update_stamina.assert_called_once_with(1, 60)
        message_sender.send_update_sta.assert_called_once_with(60)

    async def test_regenerate_stamina_at_max(self) -> None:
        """Test de regeneración cuando ya está al máximo."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(100, 100))
        player_repo.update_stamina = AsyncMock()

        service = StaminaService(player_repo)

        # Intentar regenerar cuando ya está al máximo
        await service.regenerate_stamina(1, 10)

        # No debería actualizar
        player_repo.update_stamina.assert_not_called()

    async def test_regenerate_stamina_exceeds_max(self) -> None:
        """Test de regeneración que excedería el máximo."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(95, 100))
        player_repo.update_stamina = AsyncMock()

        service = StaminaService(player_repo)

        # Regenerar más de lo que falta para el máximo
        await service.regenerate_stamina(1, 10)

        # Debería limitarse al máximo
        player_repo.update_stamina.assert_called_once_with(1, 100)

    async def test_regenerate_stamina_without_message_sender(self) -> None:
        """Test de regeneración sin message_sender."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_stamina = AsyncMock(return_value=(50, 100))
        player_repo.update_stamina = AsyncMock()

        service = StaminaService(player_repo)

        # Regenerar sin message_sender
        await service.regenerate_stamina(1, 10)

        player_repo.update_stamina.assert_called_once_with(1, 60)

    async def test_should_regenerate_with_hunger_and_water(self) -> None:
        """Test de verificación de regeneración con hambre y sed."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_hunger_thirst = AsyncMock(return_value={"min_hunger": 50, "min_water": 50})

        service = StaminaService(player_repo)

        result = await service.should_regenerate(1)

        assert result is True

    async def test_should_regenerate_without_hunger(self) -> None:
        """Test de verificación sin hambre."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_hunger_thirst = AsyncMock(return_value={"min_hunger": 0, "min_water": 50})

        service = StaminaService(player_repo)

        result = await service.should_regenerate(1)

        assert result is False

    async def test_should_regenerate_without_water(self) -> None:
        """Test de verificación sin sed."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_hunger_thirst = AsyncMock(return_value={"min_hunger": 50, "min_water": 0})

        service = StaminaService(player_repo)

        result = await service.should_regenerate(1)

        assert result is False

    async def test_should_regenerate_no_data(self) -> None:
        """Test de verificación sin datos de hambre/sed."""
        # Mock del player_repo
        player_repo = MagicMock()
        player_repo.get_hunger_thirst = AsyncMock(return_value=None)

        service = StaminaService(player_repo)

        result = await service.should_regenerate(1)

        assert result is False


class TestStaminaConstants:
    """Tests para constantes de stamina."""

    def test_stamina_costs(self) -> None:
        """Test de valores de costos de stamina."""
        assert STAMINA_COST_WALK == 1
        assert STAMINA_COST_ATTACK == 2
        assert STAMINA_COST_SPELL == 3
        assert STAMINA_COST_WORK == 5

    def test_stamina_regen_rates(self) -> None:
        """Test de valores de regeneración de stamina."""
        assert STAMINA_REGEN_RATE == 2
        assert STAMINA_REGEN_RESTING == 5
