"""Devaluación diaria del oro en bolsillo y banco con fracciones enteras acumuladas."""

import time
from dataclasses import dataclass

from src.models.item_constants import MAX_PLAYER_GOLD

SECONDS_PER_DAY = 86_400
BASIS_POINTS = 10_000
DEFAULT_RATE_BPS = 100
MAX_BANK_GOLD = 2_147_483_647
TAX_POLICY_KEY = "config:economy:daily_tax"


def utc_day(timestamp: float | None = None) -> int:
    """Calcula el corte del servidor sin usar la zona horaria del cliente.

    Returns:
        Días completos desde el epoch UTC.
    """
    return int((time.time() if timestamp is None else timestamp) // SECONDS_PER_DAY)


@dataclass(frozen=True, slots=True)
class TaxAssessment:
    """Resultado exacto de liquidar días completos, sin I/O ni dinero negativo."""

    wallet: int
    bank: int
    charged: int
    remainder: int
    last_day: int
    days: int


def assess_tax(
    wallet: int,
    bank: int,
    last_day: int,
    today: int,
    *,
    remainder: int = 0,
    rate_bps: int = DEFAULT_RATE_BPS,
) -> TaxAssessment:
    """Liquida 1% del saldo de cada día; dividir el saldo no evita la devaluación.

    Las fracciones se acumulan sobre el conjunto de ambas cuentas. El cargo se
    distribuye proporcionalmente y nunca se impone una moneda mínima diaria.
    La misma secuencia diaria se usa online, offline y después de un apagado.

    Returns:
        Saldos, fracciones y período ya liquidados.

    Raises:
        ValueError: Ante saldos, fechas, tasa o fracciones fuera del contrato.
    """
    values = (wallet, bank, last_day, today, remainder, rate_bps)
    if (
        any(type(value) is not int for value in values)
        or not 0 <= wallet <= MAX_PLAYER_GOLD
        or not 0 <= bank <= MAX_BANK_GOLD
        or min(last_day, today) < 0
    ):
        message = "Estado de devaluación fuera de rango"
        raise ValueError(message)
    if not 0 <= remainder < BASIS_POINTS or not 0 <= rate_bps <= BASIS_POINTS:
        message = "Estado de devaluación fuera de rango"
        raise ValueError(message)
    days = max(0, today - last_day)
    charged = 0
    for _ in range(days if rate_bps else 0):
        total = wallet + bank
        if not total:
            remainder = 0
            break
        fee, remainder = divmod(total * rate_bps + remainder, BASIS_POINTS)
        fee = min(fee, total)
        wallet_fee = fee * wallet // total
        wallet -= wallet_fee
        bank -= fee - wallet_fee
        charged += fee
    return TaxAssessment(wallet, bank, charged, remainder, max(last_day, today), days)
