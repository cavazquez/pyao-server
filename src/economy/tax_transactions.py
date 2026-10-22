"""Overlay fiscal aplicado antes de planificar cualquier operación monetaria."""

import json
from collections.abc import Callable, Mapping
from typing import cast

from src.economy.ground_devaluation import ground_map_id, ground_projection, stamp_ground_gold
from src.economy.taxes import TAX_POLICY_KEY, assess_tax
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot


def money_revision_key(user_id: int) -> str:
    """Identifica la versión conjunta de bolsillo y banco.

    Returns:
        Clave observada en cada operación que pueda cambiar dinero.
    """
    return f"economy:{user_id}:revision"


def tax_key(user_id: int) -> str:
    """Identifica el historial fiscal de un personaje.

    Returns:
        Clave persistente ajena a su sesión.
    """
    return f"tax:{user_id}:state"


def receipt_key(user_id: int, day: int) -> str:
    """Identifica un recibo inmutable del período liquidado.

    Returns:
        Clave única por personaje y corte UTC.
    """
    return f"tax:{user_id}:receipt:{day}"


def resource_users(resources: tuple[Resource, ...]) -> set[int]:
    """Reconoce sólo recursos de saldo del contrato propio.

    Returns:
        Identidades de los propietarios de ambas cuentas.
    """
    users = set()
    for resource in resources:
        parts = resource.key.split(":")
        if (
            len(parts) == len(("player", "user", "user_stats"))
            and parts[1].isdigit()
            and ((parts[0], parts[2]) in {("player", "user_stats"), ("bank", "gold")})
        ):
            users.add(int(parts[1]))
    return users


def tax_resources(resources: tuple[Resource, ...], today: int) -> tuple[Resource, ...]:
    """Declara ambas cuentas y el journal en el mismo WATCH del negocio.

    Returns:
        Recursos originales con las precondiciones fiscales necesarias.

    Raises:
        ValueError: Si un recurso monetario declaró un tipo incompatible.
    """
    users = resource_users(resources)
    if not users and not any(ground_map_id(resource) for resource in resources):
        return resources
    expanded = {resource.key: resource for resource in resources}
    expanded.setdefault(TAX_POLICY_KEY, Resource(TAX_POLICY_KEY, "hash"))
    for user_id in sorted(users):
        for resource in (
            Resource(RedisKeys.player_user_stats(user_id), "hash"),
            Resource(RedisKeys.bank_gold(user_id), "string"),
            Resource(tax_key(user_id), "hash"),
            Resource(money_revision_key(user_id), "string"),
            Resource(receipt_key(user_id, today), "string"),
        ):
            if resource.key in expanded and expanded[resource.key].kind != resource.kind:
                message = "Tipo de recurso monetario incompatible"
                raise ValueError(message)
            expanded.setdefault(resource.key, resource)
    return tuple(expanded.values())


def tax_snapshot(
    snapshot: Snapshot, resources: tuple[Resource, ...], today: int
) -> tuple[Snapshot, dict[str, str | dict[str, str]]]:
    """Entrega al plan de negocio los saldos liquidados en el mismo commit.

    Returns:
        Snapshot proyectado y escrituras fiscales que se confirman juntas.

    Raises:
        ValueError: Si la versión o el historial persistido son incompatibles.
    """
    policy = cast("dict[str, str]", snapshot.get(TAX_POLICY_KEY) or {})
    if not policy:
        return snapshot, {}
    if policy.get("version") != "1":
        message = "Versión de devaluación incompatible"
        raise ValueError(message)
    projected = dict(snapshot)
    writes: dict[str, str | dict[str, str]] = {}
    for user_id in resource_users(resources):
        player_key, bank_key = RedisKeys.player_user_stats(user_id), RedisKeys.bank_gold(user_id)
        stats = cast("dict[str, str]", snapshot.get(player_key) or {})
        if not stats:
            continue
        state = cast("dict[str, str]", snapshot.get(tax_key(user_id)) or {})
        previous = int(state.get("last_day", policy["activation_day"]))
        if state and previous >= today:
            continue
        wallet, bank = int(stats.get("gold", 0)), int(str(snapshot.get(bank_key) or 0))
        result = assess_tax(
            wallet,
            bank,
            previous,
            today,
            remainder=int(state.get("remainder", 0)),
            rate_bps=int(policy["rate_bps"]) if policy.get("enabled") == "1" else 0,
        )
        fields = {
            "version": "1",
            "last_day": str(result.last_day),
            "remainder": str(result.remainder),
            "total_paid": str(int(state.get("total_paid", 0)) + result.charged),
        }
        if result.days:
            journal_key = receipt_key(user_id, today)
            if snapshot.get(journal_key) is not None:
                message = "Registro de devaluación existente con estado atrasado"
                raise ValueError(message)
            fields.update(
                last_charge=str(result.charged),
                last_from_day=str(previous),
                last_charge_day=str(today),
                last_receipt=journal_key,
            )
            writes[journal_key] = json.dumps(
                {
                    "user_id": user_id,
                    "from_day": previous,
                    "to_day": today,
                    "rate_bps": int(policy["rate_bps"]) if policy.get("enabled") == "1" else 0,
                    "charged": result.charged,
                    "wallet_before": wallet,
                    "bank_before": bank,
                    "wallet_after": result.wallet,
                    "bank_after": result.bank,
                },
                sort_keys=True,
            )
        writes[tax_key(user_id)] = fields
        projected[tax_key(user_id)] = {**state, **fields}
        projected[player_key] = {**stats, "gold": str(result.wallet)}
        projected[bank_key] = str(result.bank)
        if result.charged:
            writes[player_key] = {"gold": str(result.wallet)}
            writes[bank_key] = str(result.bank)
    projected, ground_writes = ground_projection(projected, resources, today)
    return projected, {**writes, **ground_writes}


def taxed_decision(
    snapshot: Snapshot,
    resources: tuple[Resource, ...],
    today: int,
    decide: Callable[[Snapshot], Decision],
) -> Decision:
    """Combina los impuestos con el negocio sin sobreescribir campos ajenos.

    Returns:
        Una decisión completa para un único EXEC y recibo.
    """
    projected, tax_writes = tax_snapshot(snapshot, resources, today)
    decision = decide(projected)
    combined: dict[str, str | dict[str, str] | set[str]] = dict(tax_writes)
    removed: dict[str, None] = {}
    for key, value in decision.writes.items():
        if value is None:
            removed[key] = None
            continue
        prior = combined.get(key)
        combined[key] = (
            {**prior, **value} if isinstance(prior, dict) and isinstance(value, dict) else value
        )
    if projected.get(TAX_POLICY_KEY):
        combined = stamp_ground_gold(combined, resources, today)
    return Decision(
        decision.result, {**stamp_money_revision(snapshot, resources, combined), **removed}
    )


def stamp_money_revision(
    snapshot: Snapshot,
    resources: tuple[Resource, ...],
    writes: Mapping[str, str | dict[str, str] | set[str]],
) -> dict[str, str | dict[str, str] | set[str]]:
    """Versiona ambos saldos dentro del mismo EXEC, incluidos impuestos y negocio.

    Returns:
        Escrituras originales con una revisión nueva sólo si cambió algún saldo.

    Raises:
        ValueError: Si la revisión persistida es inválida.
    """
    result = dict(writes)
    for user_id in resource_users(resources):
        wallet, bank = RedisKeys.player_user_stats(user_id), RedisKeys.bank_gold(user_id)
        stats = cast("dict[str, str]", snapshot.get(wallet) or {})
        before_wallet = int(stats.get("gold", 0))
        before_bank = int(str(snapshot.get(bank) or 0))
        new_stats = writes.get(wallet)
        after_wallet = (
            int(new_stats.get("gold", before_wallet))
            if isinstance(new_stats, dict)
            else before_wallet
        )
        after_bank = int(str(writes.get(bank, before_bank)))
        if (after_wallet, after_bank) != (before_wallet, before_bank):
            key = money_revision_key(user_id)
            previous = int(str(snapshot.get(key) or 0))
            if previous < 0:
                message = "Revisión monetaria persistida inválida"
                raise ValueError(message)
            result[key] = str(previous + 1)
    return result
