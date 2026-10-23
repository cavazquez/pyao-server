"""Cálculos enteros y sorteo reproducible a partir de un compromiso de 256 bits."""

import hashlib
import hmac
import json
from bisect import bisect_right
from itertools import accumulate

NPC_ID = 950
NPC_INSTANCE = "lottery-ullathorpe"
NPC_MAP, NPC_X, NPC_Y = 1, 53, 52
RANGE = 3
MIN_BET = 100
MAX_POOL = 2_147_483_647
MAX_PARTICIPANTS = 4096
AUDIT_SECONDS = 90 * 86400
IDENTITY_LENGTH = 32
SEED_BYTES = 32
CURRENT = "lottery:current"
LAST_WINNER = "lottery:last_winner"
TAX_CARRY = "lottery:tax_remainder"


def round_key(identity: str) -> str:
    """Devuelve la clave de una ronda validada.

    Returns:
        Clave sin interpolación arbitraria de datos de red.

    Raises:
        ValueError: Ante una identidad que no fue generada por el servidor.
    """
    if len(identity) != IDENTITY_LENGTH or any(c not in "0123456789abcdef" for c in identity):
        message = "Ronda de lotería inválida"
        raise ValueError(message)
    return f"lottery:round:{identity}"


def participants_key(identity: str) -> str:
    """Devuelve el hash con una entrada por personaje.

    Returns:
        Clave validada, nunca una entrada por moneda.
    """
    return round_key(identity) + ":participants"


def commission(gross: int) -> int:
    """Redondea hacia arriba el 1% acumulado.

    Returns:
        Comisión total; cobrar sólo la diferencia evita evasión por fraccionamiento.
    """
    return (gross + 99) // 100


def encode(value: object) -> str:
    """Serializa el formato canónico de la auditoría.

    Returns:
        JSON ASCII sin espacios, claves ordenadas y enteros decimales.
    """
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def proportional(amounts: dict[str, int], total: int) -> dict[str, int]:
    """Distribuye un saldo con restos mayores y desempate por ID numérico.

    Returns:
        Importes no negativos que suman exactamente total.

    Raises:
        ValueError: Si el saldo objetivo excede la reserva.
    """
    original = sum(amounts.values())
    if not 0 <= total <= original or any(v < 0 for v in amounts.values()):
        message = "Reserva de lotería inválida"
        raise ValueError(message)
    if not original:
        return dict.fromkeys(amounts, 0)
    values = {uid: amount * total // original for uid, amount in amounts.items()}
    order = sorted(amounts, key=lambda uid: (-(amounts[uid] * total % original), int(uid)))
    for uid in order[: total - sum(values.values())]:
        values[uid] += 1
    return values


def choose(entries: dict[str, dict[str, int]], number: int) -> int:
    """Busca el intervalo semiabierto sobre aportes netos ordenados por user_id.

    Returns:
        Identidad estable del ganador.

    Raises:
        ValueError: Si el boleto no pertenece al pozo.
    """
    ordered = sorted(entries, key=int)
    ends = list(accumulate(entries[uid]["net"] for uid in ordered))
    if not ends or not 0 <= number < ends[-1]:
        message = "Boleto fuera del pozo"
        raise ValueError(message)
    return int(ordered[bisect_right(ends, number)])


def draw(seed_hex: str, identity: str, snapshot_hash: str, pool: int) -> int:
    """Deriva un entero uniforme usando HMAC-SHA256 y rechazo de la cola sesgada.

    Returns:
        Boleto reproducible desde la semilla revelada después del cierre.

    Raises:
        ValueError: Si la reserva no admite un sorteo.
    """
    if not 1 <= pool <= MAX_POOL or len(bytes.fromhex(seed_hex)) != SEED_BYTES:
        message = "Parámetros de sorteo inválidos"
        raise ValueError(message)
    limit = 2**256 - (2**256 % pool)
    prefix = (
        b"pyao-lottery-v1\0"
        + identity.encode("ascii")
        + b"\0"
        + snapshot_hash.encode("ascii")
        + b"\0"
    )
    counter = 0
    while True:
        block = hmac.digest(bytes.fromhex(seed_hex), prefix + counter.to_bytes(8, "big"), "sha256")
        number = int.from_bytes(block, "big")
        if number < limit:
            return number % pool
        counter += 1


def commitment(seed_hex: str) -> str:
    """Publica SHA-256 sin revelar la semilla durante la ronda.

    Returns:
        Compromiso hexadecimal verificable después del sorteo.
    """
    return hashlib.sha256(bytes.fromhex(seed_hex)).hexdigest()
