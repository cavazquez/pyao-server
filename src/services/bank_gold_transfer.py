"""Transferencias entre saldo del jugador y banco con un commit identificado."""

from typing import TYPE_CHECKING, Any, Literal, cast

from src.models.item_constants import MAX_PLAYER_GOLD
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis

# BANK_GOLD es int32 firmado en el contrato compartido.
MAX_BANK_GOLD = 2_147_483_647


async def transfer_gold(
    redis: Redis,
    user_id: int,
    amount: int,
    direction: Literal["deposit", "withdraw"],
    identity: str,
) -> dict[str, Any]:
    """Transfiere oro sin compensaciones ni ventana entre débito y crédito.

    Returns:
        Saldos confirmados o un rechazo sin modificaciones de recursos.

    Raises:
        ValueError: Ante cantidad, identidad, saldo o dirección inválidos.
    """
    if type(amount) is not int or not 1 <= amount <= MAX_PLAYER_GOLD:
        msg = "Cantidad inválida: debe ser mayor a 0 y respetar el límite de oro"
        raise ValueError(msg)
    if direction not in {"deposit", "withdraw"} or user_id < 1:
        msg = "Transferencia inválida"
        raise ValueError(msg)
    player_key = RedisKeys.player_user_stats(user_id)
    bank_key = RedisKeys.bank_gold(user_id)

    def decide(snapshot: Snapshot) -> Decision:
        player = cast("dict[str, str]", snapshot[player_key])
        gold = int(player.get("gold", 0))
        bank = int(cast("str | None", snapshot[bank_key]) or 0)
        if not 0 <= gold <= MAX_PLAYER_GOLD or not 0 <= bank <= MAX_BANK_GOLD:
            msg = "Saldo persistido fuera de rango"
            raise ValueError(msg)
        delta = -amount if direction == "deposit" else amount
        new_gold, new_bank = gold + delta, bank - delta
        error = ""
        if new_gold < 0 or new_bank < 0:
            error = "No tienes suficiente oro para esta operación"
        elif new_gold > MAX_PLAYER_GOLD or new_bank > MAX_BANK_GOLD:
            error = "La transferencia superaría el límite de oro"
        result = {
            "applied": not error,
            "error": error,
            "player_gold": gold if error else new_gold,
            "bank_gold": bank if error else new_bank,
            "amount": amount,
        }
        writes: dict[str, str | dict[str, str]] = (
            {} if error else {player_key: {"gold": str(new_gold)}, bank_key: str(new_bank)}
        )
        return Decision(result, writes)

    return await transact(
        redis,
        (Resource(player_key, "hash"), Resource(bank_key, "string")),
        identity,
        {"user_id": user_id, "amount": amount, "direction": direction},
        decide,
    )
