"""Tests para CombatValidator."""

from src.combat_validator import CombatValidator


class TestCombatValidator:
    """Tests para CombatValidator."""

    def test_init_default_range(self) -> None:
        """Test de inicialización con rango por defecto."""
        validator = CombatValidator()

        assert validator.melee_range == 1

    def test_init_custom_range(self) -> None:
        """Test de inicialización con rango personalizado."""
        validator = CombatValidator(melee_range=3)

        assert validator.melee_range == 3

    def test_calculate_distance_same_position(self) -> None:
        """Test de distancia en la misma posición."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 50, "y": 50}

        distance = CombatValidator.calculate_distance(pos1, pos2)

        assert distance == 0

    def test_calculate_distance_horizontal(self) -> None:
        """Test de distancia horizontal."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 55, "y": 50}

        distance = CombatValidator.calculate_distance(pos1, pos2)

        assert distance == 5

    def test_calculate_distance_vertical(self) -> None:
        """Test de distancia vertical."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 50, "y": 45}

        distance = CombatValidator.calculate_distance(pos1, pos2)

        assert distance == 5

    def test_calculate_distance_diagonal(self) -> None:
        """Test de distancia diagonal (Manhattan)."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 53, "y": 54}

        # Manhattan: |53-50| + |54-50| = 3 + 4 = 7
        distance = CombatValidator.calculate_distance(pos1, pos2)

        assert distance == 7

    def test_calculate_distance_negative_coords(self) -> None:
        """Test con coordenadas negativas."""
        pos1 = {"x": 45, "y": 45}
        pos2 = {"x": 50, "y": 50}

        distance = CombatValidator.calculate_distance(pos1, pos2)

        assert distance == 10

    def test_can_attack_adjacent(self) -> None:
        """Test de ataque a posición adyacente."""
        validator = CombatValidator(melee_range=1)

        attacker = {"x": 50, "y": 50}
        target = {"x": 51, "y": 50}

        assert validator.can_attack(attacker, target) is True

    def test_can_attack_diagonal_adjacent(self) -> None:
        """Test de ataque diagonal adyacente."""
        validator = CombatValidator(melee_range=1)

        attacker = {"x": 50, "y": 50}
        target = {"x": 51, "y": 51}

        # Manhattan: |51-50| + |51-50| = 2
        # No está en rango 1
        assert validator.can_attack(attacker, target) is False

    def test_can_attack_too_far(self) -> None:
        """Test de ataque fuera de rango."""
        validator = CombatValidator(melee_range=1)

        attacker = {"x": 50, "y": 50}
        target = {"x": 52, "y": 50}

        assert validator.can_attack(attacker, target) is False

    def test_can_attack_with_longer_range(self) -> None:
        """Test de ataque con rango mayor."""
        validator = CombatValidator(melee_range=5)

        attacker = {"x": 50, "y": 50}
        target = {"x": 53, "y": 52}

        # Manhattan: |53-50| + |52-50| = 5
        assert validator.can_attack(attacker, target) is True

    def test_can_attack_same_position(self) -> None:
        """Test de ataque en la misma posición."""
        validator = CombatValidator()

        pos = {"x": 50, "y": 50}

        assert validator.can_attack(pos, pos) is True

    def test_is_in_range_within(self) -> None:
        """Test de posiciones dentro del rango."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 52, "y": 51}

        # Manhattan: 2 + 1 = 3
        assert CombatValidator.is_in_range(pos1, pos2, 3) is True
        assert CombatValidator.is_in_range(pos1, pos2, 5) is True

    def test_is_in_range_exact(self) -> None:
        """Test de posiciones exactamente en el límite."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 53, "y": 52}

        # Manhattan: 3 + 2 = 5
        assert CombatValidator.is_in_range(pos1, pos2, 5) is True

    def test_is_in_range_outside(self) -> None:
        """Test de posiciones fuera del rango."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 55, "y": 55}

        # Manhattan: 5 + 5 = 10
        assert CombatValidator.is_in_range(pos1, pos2, 5) is False

    def test_is_in_range_zero(self) -> None:
        """Test con rango cero (solo misma posición)."""
        pos1 = {"x": 50, "y": 50}
        pos2 = {"x": 50, "y": 50}
        pos3 = {"x": 51, "y": 50}

        assert CombatValidator.is_in_range(pos1, pos2, 0) is True
        assert CombatValidator.is_in_range(pos1, pos3, 0) is False
