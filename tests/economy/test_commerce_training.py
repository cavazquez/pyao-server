"""Presupuesto comercial independiente del número de paquetes enviados."""

from src.economy.commerce_training import train_commerce
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision


def train(skills, volume, action="buy", now=10000):
    """Aplica sólo el presupuesto; no exige reglas de habilidades del dataset."""
    key = RedisKeys.player_skills(1)
    result = train_commerce(Decision({"total": volume}, {}), {key: skills}, 1, 15, action, now=now)
    return {**skills, **result.writes[key]}


def test_packet_splitting_preserves_volume_budget():
    """Cien transacciones de una moneda y una de cien entrenan lo mismo."""
    single = train({}, 100)
    split = {}
    for _ in range(100):
        split = train(split, 1)
    assert split == single
    assert single["commerce:events"] == "1"


def test_purchase_resale_cycle_cannot_keep_training():
    """Una vez invertida la dirección del mismo objeto no suma más volumen."""
    skills = train({}, 100)
    skills = train(skills, 1000, "sell")
    skills = train(skills, 1000, "buy")
    assert skills["commerce:events"] == "1"
    assert "mixed" in skills["commerce:directions"]


def test_training_cap_does_not_carry_volume_into_next_window():
    """El excedente de la ventana se descarta; una nueva exige volumen nuevo."""
    skills = train({}, 100000)
    assert skills["commerce:events"] == "4"
    assert skills["commerce:remainder"] == "0"
    skills = train(skills, 1, now=10080)
    assert skills["commerce:events"] == "0"
    assert skills["commerce:remainder"] == "1"
