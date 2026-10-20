"""La representación compacta conserva el dominio, las operaciones y los bordes."""

import random

import pytest

from src.game.coordinate_mask import MASK_BYTES, CoordinateMask


def test_boundaries_set_algebra_and_binary_roundtrip() -> None:
    """El borde 100 no se pierde y las copias no comparten mutaciones."""
    points = {(1, 1), (100, 1), (1, 100), (100, 100), (50, 50)}
    layer = CoordinateMask(points)
    assert layer == points
    assert points == layer
    assert len(layer.to_bytes()) == MASK_BYTES == 1250
    restored = CoordinateMask.from_bytes(layer.to_bytes())
    restored.discard((100, 100))
    assert (100, 100) in layer
    assert (100, 100) not in restored
    assert layer | {(2, 2)} == points | {(2, 2)}
    assert layer - {(50, 50)} == points - {(50, 50)}
    assert layer & {(1, 1), (2, 2)} == {(1, 1)}
    other = CoordinateMask({(1, 1), (2, 2)})
    for target in (other, {(1, 1), (2, 2)}):
        assert layer | target == points | set(target)
        assert layer & target == points & set(target)
        assert layer - target == points - set(target)
        assert layer ^ target == points ^ set(target)
        assert target | layer == set(target) | points
        assert target & layer == set(target) & points
        assert target - layer == set(target) - points
        assert target ^ layer == set(target) ^ points
    for outside in ((0, 1), (1, 0), (101, 100), (100, 101), (True, 1)):
        assert outside not in layer
        with pytest.raises(ValueError, match="Coordenada"):
            layer.add(outside)
    with pytest.raises(ValueError, match="Máscara"):
        CoordinateMask.from_bytes(b"short")


def test_random_mutations_match_reference_set_on_every_world_coordinate() -> None:
    """Compara todas las consultas del plano después de altas/bajas/duplicados."""
    rng = random.Random(338)
    reference = set()
    layer = CoordinateMask()
    for _ in range(20000):
        point = rng.randint(1, 100), rng.randint(1, 100)
        if rng.randrange(2):
            reference.add(point)
            layer.add(point)
        else:
            reference.discard(point)
            layer.discard(point)
    assert layer == reference
    assert len(layer) == len(reference)
    for y in range(1, 101):
        for x in range(1, 101):
            assert layer.contains_xy(x, y) == ((x, y) in reference)
