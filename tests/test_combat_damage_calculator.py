"""Tests para DamageCalculator."""

from unittest.mock import patch

from src.combat_damage_calculator import DamageCalculator


class TestDamageCalculator:
    """Tests para DamageCalculator."""

    def test_init_default_values(self) -> None:
        """Test de inicialización con valores por defecto."""
        calculator = DamageCalculator()

        assert calculator.critical_chance == 0.05
        assert calculator.critical_multiplier == 1.5
        assert calculator.defense_per_level == 0.1

    def test_init_custom_values(self) -> None:
        """Test de inicialización con valores personalizados."""
        calculator = DamageCalculator(
            critical_chance=0.1,
            critical_multiplier=2.0,
            defense_per_level=0.15,
        )

        assert calculator.critical_chance == 0.1
        assert calculator.critical_multiplier == 2.0
        assert calculator.defense_per_level == 0.15

    def test_calculate_player_damage_basic(self) -> None:
        """Test de cálculo de daño básico del jugador."""
        calculator = DamageCalculator()

        with patch("src.combat_damage_calculator.random.random", return_value=1.0):
            damage, is_critical = calculator.calculate_player_damage(
                strength=20,
                weapon_damage=10,
                target_level=5,
            )

            # Daño base: (20 // 2) + 10 = 20
            # Defensa: 5 * 0.1 = 0.5 (50% reducción)
            # Daño final: 20 * 0.5 = 10
            assert damage == 10
            assert is_critical is False

    def test_calculate_player_damage_with_critical(self) -> None:
        """Test de daño con crítico."""
        calculator = DamageCalculator()

        with patch("src.combat_damage_calculator.random.random", return_value=0.01):
            damage, is_critical = calculator.calculate_player_damage(
                strength=20,
                weapon_damage=10,
                target_level=5,
            )

            # Daño base: 10 (después de defensa)
            # Crítico: 10 * 1.5 = 15
            assert damage == 15
            assert is_critical is True

    def test_calculate_player_damage_minimum(self) -> None:
        """Test que el daño mínimo es 1."""
        calculator = DamageCalculator(defense_per_level=1.0)

        with patch("src.combat_damage_calculator.random.random", return_value=1.0):
            damage, is_critical = calculator.calculate_player_damage(
                strength=2,
                weapon_damage=0,
                target_level=10,
            )

            # Aunque la defensa reduzca todo, el mínimo es 1
            assert damage == 1
            assert is_critical is False

    def test_calculate_player_damage_high_strength(self) -> None:
        """Test con fuerza alta."""
        calculator = DamageCalculator()

        with patch("src.combat_damage_calculator.random.random", return_value=1.0):
            damage, is_critical = calculator.calculate_player_damage(
                strength=100,
                weapon_damage=50,
                target_level=1,
            )

            # Daño base: (100 // 2) + 50 = 100
            # Defensa: 1 * 0.1 = 0.1 (10% reducción)
            # Daño final: 100 * 0.9 = 90
            assert damage == 90
            assert is_critical is False

    def test_calculate_npc_damage_basic(self) -> None:
        """Test de cálculo de daño básico del NPC."""
        with patch("src.combat_damage_calculator.random.uniform", return_value=1.0):
            damage = DamageCalculator.calculate_npc_damage(
                npc_level=5,
                armor_reduction=0.1,
            )

            # Daño base: 5 * 3 = 15
            # Variación: 15 * 1.0 = 15
            # Armadura: 15 * 0.9 = 13.5 → 13
            assert damage == 13

    def test_calculate_npc_damage_high_level(self) -> None:
        """Test con NPC de nivel alto."""
        with patch("src.combat_damage_calculator.random.uniform", return_value=1.0):
            damage = DamageCalculator.calculate_npc_damage(
                npc_level=20,
                armor_reduction=0.2,
            )

            # Daño base: 20 * 3 = 60
            # Variación: 60 * 1.0 = 60
            # Armadura: 60 * 0.8 = 48
            assert damage == 48

    def test_calculate_npc_damage_minimum(self) -> None:
        """Test que el daño mínimo del NPC es 1."""
        with patch("src.combat_damage_calculator.random.uniform", return_value=0.8):
            damage = DamageCalculator.calculate_npc_damage(
                npc_level=1,
                armor_reduction=0.9,
            )

            # Aunque la armadura reduzca casi todo, el mínimo es 1
            assert damage == 1

    def test_calculate_npc_damage_variation(self) -> None:
        """Test de variación aleatoria del daño."""
        # Variación baja (80%)
        with patch("src.combat_damage_calculator.random.uniform", return_value=0.8):
            damage_low = DamageCalculator.calculate_npc_damage(
                npc_level=10,
                armor_reduction=0.0,
            )

            # Daño base: 10 * 3 = 30
            # Variación: 30 * 0.8 = 24
            assert damage_low == 24

        # Variación alta (120%)
        with patch("src.combat_damage_calculator.random.uniform", return_value=1.2):
            damage_high = DamageCalculator.calculate_npc_damage(
                npc_level=10,
                armor_reduction=0.0,
            )

            # Daño base: 10 * 3 = 30
            # Variación: 30 * 1.2 = 36
            assert damage_high == 36
