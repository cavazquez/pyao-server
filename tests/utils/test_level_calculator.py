"""Tests para level_calculator."""

from unittest.mock import MagicMock

import pytest

from src.utils.level_calculator import (
    calculate_elu_for_level,
    calculate_level_from_experience,
    calculate_remaining_elu,
    calculate_total_exp_for_level,
)


@pytest.fixture
def mock_config_manager():
    """Mock de ConfigManager."""
    config = MagicMock()
    config.as_int = MagicMock(return_value=300)  # initial_elu por defecto
    config.as_float = MagicMock(return_value=1.8)  # elu_exponent por defecto
    return config


class TestCalculateEluForLevel:
    """Tests para calculate_elu_for_level."""

    def test_level_1_returns_base_elu(self, mock_config_manager):
        """Test que nivel 1 retorna el ELU base."""
        elu = calculate_elu_for_level(1, mock_config_manager)
        assert elu == 300

    def test_level_0_returns_base_elu(self, mock_config_manager):
        """Test que nivel 0 o menor retorna el ELU base."""
        elu = calculate_elu_for_level(0, mock_config_manager)
        assert elu == 300

    def test_level_negative_returns_base_elu(self, mock_config_manager):
        """Test que nivel negativo retorna el ELU base."""
        elu = calculate_elu_for_level(-1, mock_config_manager)
        assert elu == 300

    def test_level_2_calculates_elu(self, mock_config_manager):
        """Test que nivel 2 calcula ELU correctamente."""
        elu = calculate_elu_for_level(2, mock_config_manager)
        # ELU = 300 * (2^1.8) = 300 * 3.48... ≈ 1044
        assert elu > 300
        assert elu == int(300 * (2**1.8))

    def test_level_10_calculates_elu(self, mock_config_manager):
        """Test que nivel 10 calcula ELU correctamente."""
        elu = calculate_elu_for_level(10, mock_config_manager)
        # ELU = 300 * (10^1.8) = 300 * 63.09... ≈ 18927
        assert elu > 300
        assert elu == int(300 * (10**1.8))

    def test_elu_minimum_is_base_elu(self, mock_config_manager):
        """Test que el ELU nunca es menor que el base."""
        # Configurar un exponente muy pequeño que podría dar menos que base_elu
        mock_config_manager.as_float.return_value = 0.1
        elu = calculate_elu_for_level(2, mock_config_manager)
        # Aunque el cálculo dé menos, debe retornar al menos base_elu
        assert elu >= 300

    def test_custom_initial_elu(self):
        """Test con initial_elu personalizado."""
        config = MagicMock()
        config.as_int = MagicMock(return_value=500)
        config.as_float = MagicMock(return_value=1.8)

        elu = calculate_elu_for_level(1, config)
        assert elu == 500

    def test_custom_exponent(self):
        """Test con exponente personalizado."""
        config = MagicMock()
        config.as_int = MagicMock(return_value=300)
        config.as_float = MagicMock(return_value=2.0)

        elu = calculate_elu_for_level(5, config)
        # ELU = 300 * (5^2.0) = 300 * 25 = 7500
        assert elu == 7500


class TestCalculateTotalExpForLevel:
    """Tests para calculate_total_exp_for_level."""

    def test_level_1_returns_zero(self, mock_config_manager):
        """Test que nivel 1 retorna 0 experiencia."""
        total_exp = calculate_total_exp_for_level(1, mock_config_manager)
        assert total_exp == 0

    def test_level_0_returns_zero(self, mock_config_manager):
        """Test que nivel 0 o menor retorna 0."""
        total_exp = calculate_total_exp_for_level(0, mock_config_manager)
        assert total_exp == 0

    def test_level_2_sums_elu_level_1(self, mock_config_manager):
        """Test que nivel 2 suma el ELU del nivel 1."""
        total_exp = calculate_total_exp_for_level(2, mock_config_manager)
        # Solo suma el ELU del nivel 1 (300)
        assert total_exp == 300

    def test_level_3_sums_elu_levels_1_and_2(self, mock_config_manager):
        """Test que nivel 3 suma ELU de niveles 1 y 2."""
        total_exp = calculate_total_exp_for_level(3, mock_config_manager)
        # Suma ELU nivel 1 (300) + ELU nivel 2 (300 * 2^1.8)
        elu_level_1 = 300
        elu_level_2 = int(300 * (2**1.8))
        expected = elu_level_1 + elu_level_2
        assert total_exp == expected

    def test_level_5_sums_all_previous_levels(self, mock_config_manager):
        """Test que nivel 5 suma todos los niveles anteriores."""
        total_exp = calculate_total_exp_for_level(5, mock_config_manager)
        # Suma ELU de niveles 1, 2, 3, 4
        expected = sum(calculate_elu_for_level(lvl, mock_config_manager) for lvl in range(1, 5))
        assert total_exp == expected


class TestCalculateLevelFromExperience:
    """Tests para calculate_level_from_experience."""

    def test_zero_experience_returns_level_1(self, mock_config_manager):
        """Test que 0 experiencia retorna nivel 1."""
        level = calculate_level_from_experience(0, mock_config_manager)
        assert level == 1

    def test_negative_experience_returns_level_1(self, mock_config_manager):
        """Test que experiencia negativa retorna nivel 1."""
        level = calculate_level_from_experience(-100, mock_config_manager)
        assert level == 1

    def test_experience_less_than_level_1_elu_returns_level_1(self, mock_config_manager):
        """Test que experiencia menor que ELU nivel 1 retorna nivel 1."""
        level = calculate_level_from_experience(299, mock_config_manager)
        assert level == 1

    def test_experience_equal_to_level_1_elu_returns_level_2(self, mock_config_manager):
        """Test que experiencia igual a ELU nivel 1 retorna nivel 2."""
        level = calculate_level_from_experience(300, mock_config_manager)
        assert level == 2

    def test_experience_for_level_2(self, mock_config_manager):
        """Test que experiencia suficiente para nivel 2 retorna nivel 2."""
        elu_level_1 = calculate_elu_for_level(1, mock_config_manager)
        elu_level_2 = calculate_elu_for_level(2, mock_config_manager)
        total_exp = elu_level_1 + elu_level_2

        level = calculate_level_from_experience(total_exp, mock_config_manager)
        assert level == 3

    def test_experience_between_levels(self, mock_config_manager):
        """Test que experiencia entre niveles retorna el nivel correcto."""
        elu_level_1 = calculate_elu_for_level(1, mock_config_manager)
        elu_level_2 = calculate_elu_for_level(2, mock_config_manager)
        # Experiencia suficiente para nivel 2 pero no para nivel 3
        total_exp = elu_level_1 + elu_level_2 - 1

        level = calculate_level_from_experience(total_exp, mock_config_manager)
        assert level == 2

    def test_max_level_limit_255(self, mock_config_manager):
        """Test que el nivel máximo es 255."""
        # Configurar experiencia muy alta que excedería nivel 255
        # Necesitamos calcular la experiencia total para nivel 255
        total_exp_for_255 = calculate_total_exp_for_level(255, mock_config_manager)
        # Agregar experiencia adicional
        very_high_exp = total_exp_for_255 + 1000000

        level = calculate_level_from_experience(very_high_exp, mock_config_manager)
        # Debe retornar 255 como máximo
        assert level == 255

    def test_experience_exactly_at_max_level(self, mock_config_manager):
        """Test que experiencia exacta para nivel 255 retorna 255."""
        total_exp_for_255 = calculate_total_exp_for_level(255, mock_config_manager)

        level = calculate_level_from_experience(total_exp_for_255, mock_config_manager)
        assert level == 255


class TestCalculateRemainingElu:
    """Tests para calculate_remaining_elu."""

    def test_remaining_elu_at_level_start(self, mock_config_manager):
        """Test ELU restante al inicio de un nivel."""
        # Experiencia total para nivel 2
        total_exp_for_level_2 = calculate_total_exp_for_level(2, mock_config_manager)
        # ELU restante debería ser el ELU del nivel 2
        remaining = calculate_remaining_elu(total_exp_for_level_2, 2, mock_config_manager)
        elu_level_2 = calculate_elu_for_level(2, mock_config_manager)
        assert remaining == elu_level_2

    def test_remaining_elu_mid_level(self, mock_config_manager):
        """Test ELU restante a mitad de nivel."""
        total_exp_for_level_2 = calculate_total_exp_for_level(2, mock_config_manager)
        elu_level_2 = calculate_elu_for_level(2, mock_config_manager)
        # Experiencia a mitad del nivel 2
        mid_exp = total_exp_for_level_2 + (elu_level_2 // 2)

        remaining = calculate_remaining_elu(mid_exp, 2, mock_config_manager)
        # Debe quedar aproximadamente la mitad del ELU del nivel 2
        expected_remaining = elu_level_2 // 2
        assert remaining == expected_remaining

    def test_remaining_elu_at_level_end(self, mock_config_manager):
        """Test ELU restante al final de un nivel."""
        total_exp_for_level_2 = calculate_total_exp_for_level(2, mock_config_manager)
        elu_level_2 = calculate_elu_for_level(2, mock_config_manager)
        # Experiencia justo antes de subir a nivel 3
        exp_at_end = total_exp_for_level_2 + elu_level_2 - 1

        remaining = calculate_remaining_elu(exp_at_end, 2, mock_config_manager)
        assert remaining == 1

    def test_remaining_elu_level_up(self, mock_config_manager):
        """Test ELU restante cuando sube de nivel."""
        total_exp_for_level_3 = calculate_total_exp_for_level(3, mock_config_manager)

        remaining = calculate_remaining_elu(total_exp_for_level_3, 3, mock_config_manager)
        # Debe retornar el ELU del nivel 3
        elu_level_3 = calculate_elu_for_level(3, mock_config_manager)
        assert remaining == elu_level_3

    def test_remaining_elu_negative_returns_zero(self, mock_config_manager):
        """Test que ELU restante negativo retorna 0."""
        # Experiencia mayor que la necesaria para el siguiente nivel
        total_exp_for_level_2 = calculate_total_exp_for_level(2, mock_config_manager)
        elu_level_2 = calculate_elu_for_level(2, mock_config_manager)
        # Experiencia que excede el nivel 2
        excess_exp = total_exp_for_level_2 + elu_level_2 + 100

        remaining = calculate_remaining_elu(excess_exp, 2, mock_config_manager)
        # Debe retornar 0 (no puede ser negativo)
        assert remaining == 0

    def test_remaining_elu_level_1(self, mock_config_manager):
        """Test ELU restante para nivel 1."""
        # Experiencia inicial (0)
        remaining = calculate_remaining_elu(0, 1, mock_config_manager)
        # Debe retornar el ELU del nivel 1
        elu_level_1 = calculate_elu_for_level(1, mock_config_manager)
        assert remaining == elu_level_1
