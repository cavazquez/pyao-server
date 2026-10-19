"""Fracciones de devaluación que acompañan al oro entre personajes."""

from typing import TYPE_CHECKING, cast

from src.economy.ground_devaluation import split_remainder
from src.economy.tax_transactions import tax_key
from src.economy.taxes import BASIS_POINTS
from src.utils.redis_config import RedisKeys

if TYPE_CHECKING:
    from src.utils.resource_transaction import Snapshot


def move_gold_remainder(
    snapshot: Snapshot,
    source: int,
    target: int,
    amount: int,
    writes: dict[str, str | dict[str, str] | set[str]],
) -> int:
    """Mueve fracciones con un pago neto y concreta monedas ya acumuladas.

    Returns:
        Monedas reducidas por la unión de fracciones pendientes en el receptor.
    """
    source_state = cast("dict[str, str]", snapshot.get(tax_key(source)) or {})
    target_state = cast("dict[str, str]", snapshot.get(tax_key(target)) or {})
    if not source_state or not target_state or amount <= 0:
        return 0
    source_stats = cast("dict[str, str]", snapshot[RedisKeys.player_user_stats(source)])
    split = split_remainder(
        int(source_state.get("remainder", 0)),
        amount,
        int(source_stats.get("gold", 0)) + int(str(snapshot.get(RedisKeys.bank_gold(source)) or 0)),
    )
    fee, remaining = divmod(int(target_state.get("remainder", 0)) + split.moved, BASIS_POINTS)
    writes[tax_key(source)] = {"remainder": str(split.remaining)}
    writes[tax_key(target)] = {
        "remainder": str(remaining),
        "total_paid": str(int(target_state.get("total_paid", 0)) + fee),
    }
    if fee:
        key = RedisKeys.player_user_stats(target)
        changes = cast("dict[str, str]", writes[key]).copy()
        changes["gold"] = str(int(changes["gold"]) - fee)
        writes[key] = changes
    return fee
