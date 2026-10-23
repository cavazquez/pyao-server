"""Reservas, cierres y liquidaciones idempotentes en un único Redis autoritativo."""

import hashlib
import json
import secrets
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from src.economy.taxes import BASIS_POINTS, MAX_BANK_GOLD, TAX_POLICY_KEY, utc_day
from src.models.item_constants import MAX_PLAYER_GOLD
from src.services.lottery.rules import (
    AUDIT_SECONDS,
    CURRENT,
    LAST_WINNER,
    MAX_PARTICIPANTS,
    MAX_POOL,
    MIN_BET,
    NPC_ID,
    NPC_INSTANCE,
    RANGE,
    TAX_CARRY,
    choose,
    commission,
    commitment,
    draw,
    encode,
    participants_key,
    proportional,
    round_key,
)
from src.utils.durability import require_durable
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys
from src.utils.resource_transaction import Decision, Resource, Snapshot, transact

if TYPE_CHECKING:
    from redis.asyncio import Redis


MAX_REASON_LENGTH = 200


def fields(snapshot: Snapshot, key: str) -> dict[str, str]:
    """Resuelve un hash ya observado.

    Returns:
        Campos Redis o un hash vacío.
    """
    return cast("dict[str, str]", snapshot.get(key) or {})


def entries(snapshot: Snapshot, key: str) -> dict[str, dict[str, int]]:
    """Decodifica una entrada por personaje.

    Returns:
        Participaciones enteras, sin datos ejecutables.
    """
    return {uid: json.loads(value) for uid, value in fields(snapshot, key).items()}


def rejected(message: str) -> Decision:
    """Construye un rechazo que no modifica recursos de negocio.

    Returns:
        Resultado público guardable como comprobante.
    """
    return Decision({"applied": False, "message": message}, {})


def nearby(
    stats: dict[str, str], position: dict[str, str], npc: dict[str, str], target: dict[str, str]
) -> bool:
    """Comprueba identidad exacta, selección, vida y alcance en el snapshot WATCH.

    Returns:
        Si la apuesta procede del puesto activo y de un personaje vivo próximo.
    """
    return bool(
        int(stats.get("min_hp", 0)) > 0
        and npc.get("instance_id") == NPC_INSTANCE == target.get("npc")
        and int(npc.get("char_index", -1)) == int(target.get("index", -2))
        and int(npc.get("npc_id", 0)) == NPC_ID
        and npc.get("role") == "lottery"
        and npc.get("is_hostile") == "False"
        and npc.get("is_attackable") == "False"
        and int(npc.get("hp", 0)) > 0
        and not npc.get("death_state")
        and position.get("map") == npc.get("map_id")
        and max(
            abs(int(position.get("x", 0)) - int(npc.get("x", -999))),
            abs(int(position.get("y", 0)) - int(npc.get("y", -999))),
        )
        <= RANGE
    )


class LotteryRepository:
    """La sesión no posee pozo ni caché de saldos; Redis sobrevive a sus workers."""

    def __init__(
        self, redis: Redis, *, seconds: int = 300, clock: Callable[[], float] = time.time
    ) -> None:
        """Inyecta sólo reloj en pruebas; la semilla productiva viene de secrets."""
        self.redis, self.seconds, self.clock = redis, seconds, clock

    async def commit(
        self,
        resources: tuple[Resource, ...],
        request: dict[str, Any],
        decide: Callable[[Snapshot], Decision],
        identity: str | None = None,
    ) -> dict[str, Any]:
        """Confirma el recibo y exige fsync incluso al recuperar una respuesta perdida.

        Returns:
            Resultado durable, sin inferir que una desconexión deshizo EXEC.
        """
        result = await transact(self.redis, resources, identity or operation_id(), request, decide)
        await require_durable(self.redis)
        return result

    async def current(self) -> str:
        """Prepublica un compromiso persistente sin iniciar el reloj de apuestas.

        Returns:
            Ronda actual; no reemplaza rondas abiertas ni premios pendientes.
        """
        existing = await self.redis.get(CURRENT)
        if existing:
            round_key(str(existing))
            return str(existing)
        identity, seed = uuid4().hex, secrets.token_hex(32)
        key = round_key(identity)

        def decide(snapshot: Snapshot) -> Decision:
            if snapshot[CURRENT]:
                return Decision({"round": snapshot[CURRENT]}, {})
            return Decision(
                {"round": identity},
                {
                    CURRENT: identity,
                    key: {
                        "version": "1",
                        "status": "open",
                        "id": identity,
                        "seed": seed,
                        "commitment": commitment(seed),
                        "seconds": str(self.seconds),
                        "closes_at": "0",
                        "opened_at": "0",
                        "pool": "0",
                        "fees": "0",
                        "gross": "0",
                        "count": "0",
                        "day": str(utc_day(self.clock())),
                        "devalued": "0",
                    },
                },
            )

        result = await self.commit(
            (Resource(CURRENT, "string"), Resource(key, "hash")),
            {"action": "lottery.prepare"},
            decide,
        )
        return str(result["round"])

    async def bet(
        self, user: int, identity: str, round_id: str, npc_id: str, gross: int
    ) -> dict[str, Any]:
        """Descuenta bruto y reserva neto/comisión junto con el comprobante.

        Returns:
            Cobro original en cada reintento, incluso después de cerrar/alejarse.
        """
        key, participants = round_key(round_id), participants_key(round_id)
        stats, position = RedisKeys.player_user_stats(user), RedisKeys.player_position(user)
        npc, target = RedisKeys.npc_instance(NPC_INSTANCE), f"chat:target:{user}"
        resources = (
            Resource(CURRENT, "string"),
            Resource(key, "hash"),
            Resource(participants, "hash", fields=(str(user),)),
            Resource(stats, "hash"),
            Resource(position, "hash"),
            Resource(npc, "hash"),
            Resource(target, "hash"),
        )

        def decide(snapshot: Snapshot) -> Decision:
            state, actor = fields(snapshot, key), fields(snapshot, stats)
            if npc_id != NPC_INSTANCE or not nearby(
                actor, fields(snapshot, position), fields(snapshot, npc), fields(snapshot, target)
            ):
                return rejected(
                    "Seleccioná al Lotero de Ullathorpe y acercate vivo a tres casillas."
                )
            now = int(self.clock())
            deadline = int(state.get("closes_at", 0))
            if (
                snapshot[CURRENT] != round_id
                or state.get("status") != "open"
                or (deadline and now >= deadline)
                or int(state.get("day", -1)) != utc_day(now)
            ):
                return rejected("La ronda cerró o cambió de día; actualizá el puesto.")
            if (
                type(gross) is not int
                or not MIN_BET <= gross <= MAX_POOL
                or int(actor.get("gold", 0)) < gross
            ):
                return rejected("Apuesta mínima 100; el bruto no puede superar tu oro disponible.")
            previous = entries(snapshot, participants).get(
                str(user), {"gross": 0, "fee": 0, "net": 0}
            )
            fee = commission(previous["gross"] + gross) - previous["fee"]
            net = gross - fee
            if int(state["gross"]) + gross > MAX_POOL or (
                not previous["gross"] and int(state["count"]) >= MAX_PARTICIPANTS
            ):
                return rejected("La ronda alcanzó su límite de oro o participantes.")
            updated = {
                "gross": previous["gross"] + gross,
                "fee": previous["fee"] + fee,
                "net": previous["net"] + net,
            }
            result = {
                "applied": True,
                "message": f"Apuesta confirmada: {gross} oro; comisión {fee}, neto {net}.",
                "round": round_id,
                "gross": gross,
                "fee": fee,
                "net": net,
                "receipt": identity,
            }
            return Decision(
                result,
                {
                    stats: {"gold": str(int(actor["gold"]) - gross)},
                    key: {
                        "pool": str(int(state["pool"]) + net),
                        "fees": str(int(state["fees"]) + fee),
                        "gross": str(int(state["gross"]) + gross),
                        "count": str(int(state["count"]) + (not previous["gross"])),
                        "opened_at": state["opened_at"] if deadline else str(now),
                        "closes_at": str(deadline or now + int(state["seconds"])),
                    },
                    participants: {str(user): encode(updated)},
                },
            )

        return await self.commit(
            resources,
            {
                "action": "lottery.bet",
                "user": user,
                "round": round_id,
                "npc": npc_id,
                "gross": gross,
            },
            decide,
            identity,
        )

    async def refresh(self, round_id: str) -> None:
        """Devalúa reservas abiertas/pendientes una vez por corte UTC, sin evasión."""
        key, participants = round_key(round_id), participants_key(round_id)
        today = utc_day(self.clock())
        if int(await self.redis.hget(key, "day") or today) >= today:
            return

        def decide(snapshot: Snapshot) -> Decision:
            state, policy = fields(snapshot, key), fields(snapshot, TAX_POLICY_KEY)
            if state.get("status") not in {"open", "pending", "cancelling"}:
                return Decision({}, {})
            rows = entries(snapshot, participants)
            pool, remainder = int(state["pool"]), int(str(snapshot[TAX_CARRY] or 0))
            rate = int(policy.get("rate_bps", 100)) if policy.get("enabled", "1") == "1" else 0
            before = pool
            for _ in range(max(0, today - int(state["day"]))):
                charge, remainder = divmod(pool * rate + remainder, BASIS_POINTS)
                pool -= min(charge, pool)
                if not pool:
                    break
            values = proportional({uid: row["net"] for uid, row in rows.items()}, pool)
            return Decision(
                {},
                {
                    key: {
                        "pool": str(pool),
                        "day": str(today),
                        "devalued": str(int(state["devalued"]) + before - pool),
                    },
                    TAX_CARRY: str(remainder),
                    participants: {
                        uid: encode({**row, "net": values[uid]}) for uid, row in rows.items()
                    },
                },
            )

        await self.commit(
            (
                Resource(key, "hash"),
                Resource(participants, "hash"),
                Resource(TAX_POLICY_KEY, "hash"),
                Resource(TAX_CARRY, "string"),
            ),
            {"action": "lottery.devalue", "round": round_id, "day": today},
            decide,
        )

    async def close(self, round_id: str) -> None:
        """Congela participaciones y una única intención de pago verificable."""
        key, participants = round_key(round_id), participants_key(round_id)

        def decide(snapshot: Snapshot) -> Decision:
            state = fields(snapshot, key)
            if (
                state.get("status") != "open"
                or not int(state["closes_at"])
                or self.clock() < int(state["closes_at"])
                or int(state["day"]) != utc_day(self.clock())
            ):
                return Decision({}, {})
            rows = entries(snapshot, participants)
            frozen = encode([[int(uid), rows[uid]] for uid in sorted(rows, key=int)])
            digest = hashlib.sha256(frozen.encode("ascii")).hexdigest()
            pool = int(state["pool"])
            if not pool:
                summary = {
                    "round": round_id,
                    "status": "cancelled",
                    "reason": "Pozo agotado por devaluación",
                    "gross": int(state["gross"]),
                    "fees": int(state["fees"]),
                    "devalued": int(state["devalued"]),
                }
                return Decision(
                    {},
                    {
                        key: {"status": "cancelled", "reason": str(summary["reason"])},
                        f"lottery:summary:{round_id}": encode(summary),
                    },
                )
            number = draw(state["seed"], round_id, digest, pool)
            winner = choose(rows, number)
            return Decision(
                {},
                {
                    key: {
                        "status": "pending",
                        "snapshot_hash": digest,
                        "number": str(number),
                        "winner": str(winner),
                        "draw_pool": str(pool),
                        "drawn_at": str(int(self.clock())),
                    },
                    f"{key}:snapshot": frozen,
                },
            )

        await self.commit(
            (
                Resource(key, "hash"),
                Resource(participants, "hash"),
                Resource(f"lottery:summary:{round_id}", "string"),
                Resource(f"{key}:snapshot", "string"),
            ),
            {"action": "lottery.close", "round": round_id},
            decide,
        )

    async def pay(self, round_id: str) -> dict[str, Any]:
        """Acredita TODO el pozo offline; si faltan topes conserva el premio reservado.

        Returns:
            Pago durable o motivo de reserva pendiente, sin redibujar el ganador.
        """
        key = round_key(round_id)
        user = int(await self.redis.hget(key, "winner") or 0)
        if not user:
            return {"applied": False}
        name = str(await self.redis.hget("account:index:user_id", str(user)) or "")
        account = RedisKeys.account_data(name)
        stats, bank = RedisKeys.player_user_stats(user), RedisKeys.bank_gold(user)
        summary = f"lottery:summary:{round_id}"

        def decide(snapshot: Snapshot) -> Decision:
            state, actor = fields(snapshot, key), fields(snapshot, stats)
            if (
                state.get("status") != "pending"
                or int(state.get("winner", 0)) != user
                or int(state["day"]) != utc_day(self.clock())
            ):
                return rejected("El premio ya se pagó o requiere actualizar la reserva.")
            if (
                not actor
                or fields(snapshot, account).get("user_id") != str(user)
                or fields(snapshot, "account:index:user_id").get(str(user)) != name
            ):
                return rejected("Premio reservado: la identidad del ganador requiere revisión.")
            pool = int(state["pool"])
            wallet, savings = int(actor.get("gold", 0)), int(str(snapshot[bank] or 0))
            in_wallet = min(pool, MAX_PLAYER_GOLD - wallet)
            in_bank = pool - in_wallet
            if savings + in_bank > MAX_BANK_GOLD:
                return rejected("Premio reservado: liberá capacidad en bolsillo o banco.")
            result = {
                "user": user,
                "name": name,
                "prize": pool,
                "round": round_id,
                "at": int(self.clock()),
                "commitment": state["commitment"],
                "seed": state["seed"],
                "snapshot_hash": state["snapshot_hash"],
                "number": int(state["number"]),
                "draw_pool": int(state["draw_pool"]),
                "fees": int(state["fees"]),
                "devalued": int(state["devalued"]),
                "gross": int(state["gross"]),
            }
            return Decision(
                {"applied": True, **result},
                {
                    stats: {"gold": str(wallet + in_wallet)},
                    bank: str(savings + in_bank),
                    key: {"status": "paid", "paid_at": str(result["at"]), "paid": str(pool)},
                    LAST_WINNER: encode(result),
                    summary: encode(result),
                },
            )

        return await self.commit(
            (
                Resource(key, "hash"),
                Resource(stats, "hash"),
                Resource(bank, "string"),
                Resource(account, "hash"),
                Resource("account:index:user_id", "hash", fields=(str(user),)),
                Resource(LAST_WINNER, "string"),
                Resource(summary, "string"),
            ),
            {"action": "lottery.pay", "round": round_id, "user": user},
            decide,
        )

    async def advance(self) -> None:
        """Recupera rondas y pagos después de reiniciar sin depender de conexiones."""
        round_id = await self.current()
        await self.refresh(round_id)
        state = await self.redis.hgetall(round_key(round_id))
        if (
            state.get("status") == "open"
            and int(state["closes_at"])
            and self.clock() >= int(state["closes_at"])
        ):
            await self.close(round_id)
            state = await self.redis.hgetall(round_key(round_id))
        if state.get("status") == "pending":
            await self.pay(round_id)
            state = await self.redis.hgetall(round_key(round_id))
        if state.get("status") == "cancelling":
            await self.refund(round_id)
            state = await self.redis.hgetall(round_key(round_id))
        if state.get("status") in {"paid", "cancelled"}:
            await self.retire(round_id)

    async def retire(self, round_id: str) -> None:
        """Libera sólo una ronda ya liquidada y retiene su auditoría noventa días."""
        key = round_key(round_id)

        def decide(snapshot: Snapshot) -> Decision:
            state = fields(snapshot, key)
            if snapshot[CURRENT] != round_id or state.get("status") not in {"paid", "cancelled"}:
                return Decision({}, {})
            return Decision({}, {CURRENT: None})

        await self.commit(
            (Resource(CURRENT, "string", deletable=True), Resource(key, "hash")),
            {"action": "lottery.retire", "round": round_id},
            decide,
        )
        await self.redis.expire(key, AUDIT_SECONDS)
        await self.redis.expire(participants_key(round_id), AUDIT_SECONDS)
        await self.redis.expire(f"{key}:snapshot", AUDIT_SECONDS)

    async def cancel(self, round_id: str, reason: str) -> dict[str, Any]:
        """Reserva reembolsos completos; sólo API de operador, nunca paquete de jugador.

        Returns:
            Confirmación durable de la intención o rechazo si ya hubo sorteo.

        Raises:
            ValueError: Si falta una razón auditable de cancelación.
        """
        if not reason.strip() or len(reason) > MAX_REASON_LENGTH:
            message = "La cancelación requiere una razón de hasta 200 caracteres"
            raise ValueError(message)
        key = round_key(round_id)

        def decide(snapshot: Snapshot) -> Decision:
            if fields(snapshot, key).get("status") != "open":
                return rejected("Sólo puede cancelarse una ronda sin sorteo confirmado.")
            return Decision(
                {"applied": True},
                {
                    key: {
                        "status": "cancelling",
                        "reason": reason,
                        "cancelled_at": str(int(self.clock())),
                    }
                },
            )

        return await self.commit(
            (Resource(key, "hash"),),
            {"action": "lottery.cancel", "round": round_id, "reason": reason},
            decide,
        )

    async def refund(self, round_id: str) -> None:
        """Reembolsa una reserva por turno con marcación atómica y capacidad completa."""
        key, participants = round_key(round_id), participants_key(round_id)
        rows = {
            uid: json.loads(value)
            for uid, value in (await self.redis.hgetall(participants)).items()
        }
        user = next((int(uid) for uid, row in rows.items() if not row.get("refunded")), 0)
        if not user:
            summary = f"lottery:summary:{round_id}"

            def finish(snapshot: Snapshot) -> Decision:
                state = fields(snapshot, key)
                if state.get("status") != "cancelling" or any(
                    not row.get("refunded") for row in entries(snapshot, participants).values()
                ):
                    return Decision({}, {})
                return Decision(
                    {},
                    {
                        key: {"status": "cancelled"},
                        summary: encode(
                            {
                                "round": round_id,
                                "status": "cancelled",
                                "gross": int(state["gross"]),
                                "devalued": int(state["devalued"]),
                                "reason": state["reason"],
                            }
                        ),
                    },
                )

            await self.commit(
                (
                    Resource(key, "hash"),
                    Resource(participants, "hash"),
                    Resource(summary, "string"),
                ),
                {"action": "lottery.refund.finish", "round": round_id},
                finish,
            )
            return
        stats, bank = RedisKeys.player_user_stats(user), RedisKeys.bank_gold(user)
        name = str(await self.redis.hget("account:index:user_id", str(user)) or "")
        account = RedisKeys.account_data(name)

        def decide(snapshot: Snapshot) -> Decision:
            state, actor = fields(snapshot, key), fields(snapshot, stats)
            row = entries(snapshot, participants).get(str(user), {})
            if (
                state.get("status") != "cancelling"
                or row.get("refunded")
                or not row
                or int(state["day"]) != utc_day(self.clock())
            ):
                return Decision({}, {})
            if (
                not actor
                or fields(snapshot, account).get("user_id") != str(user)
                or fields(snapshot, "account:index:user_id").get(str(user)) != name
            ):
                return rejected("Reembolso reservado: identidad pendiente de revisión.")
            amount = row["net"] + row["fee"]
            wallet, savings = int(actor.get("gold", 0)), int(str(snapshot[bank] or 0))
            in_wallet = min(amount, MAX_PLAYER_GOLD - wallet)
            if savings + amount - in_wallet > MAX_BANK_GOLD:
                return rejected("Reembolso reservado: no hay capacidad suficiente.")
            return Decision(
                {"applied": True},
                {
                    stats: {"gold": str(wallet + in_wallet)},
                    bank: str(savings + amount - in_wallet),
                    participants: {str(user): encode({**row, "net": 0, "refunded": amount})},
                    key: {
                        "pool": str(int(state["pool"]) - row["net"]),
                        "fees": str(int(state["fees"]) - row["fee"]),
                    },
                },
            )

        await self.commit(
            (
                Resource(key, "hash"),
                Resource(participants, "hash", fields=(str(user),)),
                Resource(stats, "hash"),
                Resource(bank, "string"),
                Resource(account, "hash"),
                Resource("account:index:user_id", "hash", fields=(str(user),)),
            ),
            {"action": "lottery.refund", "round": round_id, "user": user},
            decide,
        )
