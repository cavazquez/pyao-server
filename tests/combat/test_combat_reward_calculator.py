"""Tests para RewardCalculator."""

from unittest.mock import patch

from src.combat.combat_reward_calculator import RewardCalculator


class TestRewardCalculator:
    """Tests para RewardCalculator."""

    def test_init_default_values(self) -> None:
        """Test de inicialización con valores por defecto."""
        calculator = RewardCalculator()

        assert calculator.exp_per_level == 10
        assert calculator.gold_per_level == 5

    def test_init_custom_values(self) -> None:
        """Test de inicialización con valores personalizados."""
        calculator = RewardCalculator(exp_per_level=20, gold_per_level=10)

        assert calculator.exp_per_level == 20
        assert calculator.gold_per_level == 10

    def test_calculate_experience_level_1(self) -> None:
        """Test de cálculo de experiencia para nivel 1."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=0):
            exp = calculator.calculate_experience(1)

            # Exp base: 1 * 10 = 10
            # Bonus: 0
            assert exp == 10

    def test_calculate_experience_level_5(self) -> None:
        """Test de cálculo de experiencia para nivel 5."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=5):
            exp = calculator.calculate_experience(5)

            # Exp base: 5 * 10 = 50
            # Bonus: 5
            assert exp == 55

    def test_calculate_experience_level_10(self) -> None:
        """Test de cálculo de experiencia para nivel 10."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=10):
            exp = calculator.calculate_experience(10)

            # Exp base: 10 * 10 = 100
            # Bonus: 10
            assert exp == 110

    def test_calculate_experience_with_custom_rate(self) -> None:
        """Test con tasa de experiencia personalizada."""
        calculator = RewardCalculator(exp_per_level=20)

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=0):
            exp = calculator.calculate_experience(5)

            # Exp base: 5 * 20 = 100
            assert exp == 100

    def test_calculate_experience_bonus_range(self) -> None:
        """Test que el bonus está en el rango correcto."""
        calculator = RewardCalculator()

        # Bonus mínimo (0)
        with patch("src.combat.combat_reward_calculator.random.randint", return_value=0):
            exp_min = calculator.calculate_experience(5)
            assert exp_min == 50

        # Bonus máximo (nivel * 2)
        with patch("src.combat.combat_reward_calculator.random.randint", return_value=10):
            exp_max = calculator.calculate_experience(5)
            assert exp_max == 60

    def test_calculate_gold_drop_level_1(self) -> None:
        """Test de cálculo de oro para nivel 1."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=1):
            gold = calculator.calculate_gold_drop(1)

            # Oro base: 1 * 5 = 5
            # Bonus: 1
            assert gold == 6

    def test_calculate_gold_drop_level_5(self) -> None:
        """Test de cálculo de oro para nivel 5."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=25):
            gold = calculator.calculate_gold_drop(5)

            # Oro base: 5 * 5 = 25
            # Bonus: 25
            assert gold == 50

    def test_calculate_gold_drop_level_10(self) -> None:
        """Test de cálculo de oro para nivel 10."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=50):
            gold = calculator.calculate_gold_drop(10)

            # Oro base: 10 * 5 = 50
            # Bonus: 50
            assert gold == 100

    def test_calculate_gold_drop_with_custom_rate(self) -> None:
        """Test con tasa de oro personalizada."""
        calculator = RewardCalculator(gold_per_level=10)

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=1):
            gold = calculator.calculate_gold_drop(5)

            # Oro base: 5 * 10 = 50
            # Bonus: 1
            assert gold == 51

    def test_calculate_gold_drop_bonus_range(self) -> None:
        """Test que el bonus de oro está en el rango correcto."""
        calculator = RewardCalculator()

        # Bonus mínimo (1)
        with patch("src.combat.combat_reward_calculator.random.randint", return_value=1):
            gold_min = calculator.calculate_gold_drop(5)
            assert gold_min == 26  # 25 + 1

        # Bonus máximo (50)
        with patch("src.combat.combat_reward_calculator.random.randint", return_value=50):
            gold_max = calculator.calculate_gold_drop(5)
            assert gold_max == 75  # 25 + 50

    def test_high_level_rewards(self) -> None:
        """Test de recompensas para niveles altos."""
        calculator = RewardCalculator()

        with patch("src.combat.combat_reward_calculator.random.randint", return_value=20):
            exp = calculator.calculate_experience(20)
            gold = calculator.calculate_gold_drop(20)

            # Exp: 20 * 10 + 20 = 220
            # Gold: 20 * 5 + 20 = 120
            assert exp == 220
            assert gold == 120
