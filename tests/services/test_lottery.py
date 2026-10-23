"""Economía, límites, reintentos y recuperación de lotería con Redis propio."""

import asyncio
import hashlib
import json
import os
import random
import time
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from src.config.game_config import RedisConfig
from src.economy.taxes import MAX_BANK_GOLD
from src.models.item_constants import MAX_PLAYER_GOLD
from src.operations.redis_sandbox import RedisSandbox, docker
from src.services.lottery.repository import LotteryRepository
from src.services.lottery.rules import (
    CURRENT,
    LAST_WINNER,
    MAX_POOL,
    NPC_INSTANCE,
    choose,
    commission,
    commitment,
    draw,
    encode,
    participants_key,
    proportional,
    round_key,
)
from src.utils.gold_atomic import operation_id
from src.utils.resource_transaction import Decision, Resource, transact


@pytest.fixture(scope="module")
def lottery_sandbox():
    """Usa un contenedor AOF propio sólo cuando se solicita la campaña real.

    Yields:
        Sandbox aislado o None para las pruebas rápidas.
    """
    if os.environ.get("PYAO_RUN_LOTTERY_REDIS") != "1":
        yield None
        return
    with RedisSandbox() as sandbox:
        yield sandbox


@pytest_asyncio.fixture
async def game(redis_client, lottery_sandbox):
    """Prepara dos identidades sin depender de cuentas del operador.

    Yields:
        Reloj controlado y repositorio productivo con dos personajes próximos.
    """
    if lottery_sandbox is not None:
        await redis_client.redis.aclose()
        redis_client._redis = None
        await redis_client.connect(
            RedisConfig(
                host="127.0.0.1",
                port=lottery_sandbox.port,
                password_file=lottery_sandbox.password_file,
            ),
            seed_defaults=False,
        )
        await redis_client.redis.flushdb()  # Instancia creada exclusivamente por este módulo.
    now = [int(time.time())]
    repo = LotteryRepository(redis_client.redis, clock=lambda: now[0])
    with (
        patch("src.services.lottery.repository.require_durable", AsyncMock())
        if lottery_sandbox is None
        else nullcontext()
    ):
        for user in (1, 2):
            await repo.redis.hset(
                f"player:{user}:user_stats", mapping={"gold": "10000", "min_hp": "100"}
            )
            await repo.redis.hset(
                f"player:{user}:position", mapping={"map": "1", "x": str(51 + user), "y": "53"}
            )
            await repo.redis.hset(
                f"chat:target:{user}", mapping={"npc": NPC_INSTANCE, "index": "10100"}
            )
            await repo.redis.hset("account:index:user_id", str(user), f"Player{user}")
            await repo.redis.hset(
                f"account:Player{user}:data",
                mapping={"user_id": str(user), "username": f"Player{user}"},
            )
        await repo.redis.hset(
            f"npc:instance:{NPC_INSTANCE}",
            mapping={
                "npc_id": "950",
                "instance_id": NPC_INSTANCE,
                "char_index": "10100",
                "map_id": "1",
                "x": "53",
                "y": "52",
                "hp": "100",
                "role": "lottery",
                "is_hostile": "False",
                "is_attackable": "False",
            },
        )
        yield SimpleNamespace(
            repo=repo, redis=repo.redis, now=now, client=redis_client, sandbox=lottery_sandbox
        )
    if lottery_sandbox:
        await redis_client.disconnect()


async def bet(game, user=1, gross=100, *, identity=None, round_id=None, npc=NPC_INSTANCE):
    """Envía una petición de apuesta al repositorio con identidad válida.

    Returns:
        Comprobante del commit.
    """
    return await game.repo.bet(
        user, identity or operation_id(), round_id or await game.repo.current(), npc, gross
    )


@pytest.mark.asyncio
async def test_round_precommits_without_timer_and_concurrent_creation(game):
    """Dos workers observan el mismo compromiso y no abren el plazo sin dinero."""
    ids = await asyncio.gather(*(game.repo.current() for _ in range(4)))
    assert len(set(ids)) == 1
    state = await game.redis.hgetall(round_key(ids[0]))
    assert state["commitment"] == commitment(state["seed"])
    assert state["closes_at"] == "0"
    game.now[0] += 1000
    await game.repo.advance()
    assert await game.redis.get(CURRENT) == ids[0]


@pytest.mark.asyncio
async def test_100_plus_300_receipt_replay_after_leaving_and_draw(game):
    """400=4+396; alejarse/cerrar no invalida un comprobante ya confirmado."""
    rid = await game.repo.current()
    identity = operation_id()
    a = await bet(game, identity=identity, round_id=rid)
    b = await bet(game, user=2, gross=300, round_id=rid)
    assert (a["net"], b["net"], a["fee"], b["fee"]) == (99, 297, 1, 3)
    state = await game.redis.hgetall(round_key(rid))
    assert (int(state["pool"]), int(state["fees"]), int(state["gross"])) == (396, 4, 400)
    await game.redis.hset("player:1:position", "map", "2")
    game.now[0] = int(state["closes_at"])
    await game.repo.close(rid)
    assert await bet(game, identity=identity, round_id=rid) == a
    with pytest.raises(ValueError, match="reutilizado"):
        await bet(game, identity=identity, gross=200, round_id=rid)
    await game.repo.pay(rid)
    winner = json.loads(await game.redis.get(LAST_WINNER))
    assert winner["prize"] == 396
    balances = [int(await game.redis.hget(f"player:{u}:user_stats", "gold")) for u in (1, 2)]
    assert sum(balances) == 19996
    await game.repo.pay(rid)
    assert balances == [
        int(await game.redis.hget(f"player:{u}:user_stats", "gold")) for u in (1, 2)
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("key", "field", "value"),
    [
        ("player:1:position", "map", "2"),
        ("player:1:position", "x", "70"),
        ("player:1:user_stats", "min_hp", "0"),
        ("chat:target:1", "npc", "forged"),
        ("chat:target:1", "index", "999"),
        (f"npc:instance:{NPC_INSTANCE}", "hp", "0"),
        (f"npc:instance:{NPC_INSTANCE}", "role", "inhabitant"),
        (f"npc:instance:{NPC_INSTANCE}", "is_hostile", "True"),
    ],
)
async def test_physical_rejections_do_not_debit(game, key, field, value):
    """Precondiciones observadas dentro de WATCH, sin saldo negativo ni apuestas."""
    await game.redis.hset(key, field, value)
    assert not (await bet(game))["applied"]
    assert await game.redis.hget("player:1:user_stats", "gold") == "10000"


@pytest.mark.asyncio
@pytest.mark.parametrize("gross", [-1, 0, 99, 10001, MAX_POOL + 1, True])
async def test_invalid_amounts_and_forged_npc(game, gross):
    """Ni booleanos ni importes fuera de rango autorizan un débito."""
    assert not (await bet(game, gross=gross))["applied"]
    assert not (await bet(game, npc="another-instance"))["applied"]
    assert await game.redis.hget("player:1:user_stats", "gold") == "10000"


@pytest.mark.asyncio
async def test_cumulative_fee_and_own_field_only(game):
    """101+199 pagan lo mismo que 300, sin reemplazar a otros participantes."""
    first = await bet(game, gross=101)
    await bet(game, user=2)
    second = await bet(game, gross=199)
    assert first["fee"] + second["fee"] == commission(300) == 3
    rid = await game.repo.current()
    rows = await game.redis.hgetall(participants_key(rid))
    assert len(rows) == 2
    assert json.loads(rows["2"])["net"] == 99


@pytest.mark.asyncio
@pytest.mark.parametrize("offset", [-1, 0, 1])
async def test_authoritative_closing_boundary(game, offset):
    """T-1 entra; T/T+1 rechazan y el reloj no se extiende al apostar."""
    await bet(game)
    rid = await game.repo.current()
    deadline = int(await game.redis.hget(round_key(rid), "closes_at"))
    game.now[0] = deadline + offset
    assert (await bet(game, user=2))["applied"] is (offset < 0)
    assert int(await game.redis.hget(round_key(rid), "closes_at")) == deadline


@pytest.mark.asyncio
async def test_two_workers_close_and_pay_once_after_offline_rename(game):
    """Un participante cobra desconectado por ID, usando nombre público al pagar."""
    await bet(game)
    rid = await game.repo.current()
    game.now[0] += 300
    other = LotteryRepository(game.redis, clock=lambda: game.now[0])
    await asyncio.gather(game.repo.close(rid), other.close(rid))
    frozen = await game.redis.hgetall(round_key(rid))
    await game.redis.hset("account:index:user_id", "1", "Renamed")
    await game.redis.hset("account:Renamed:data", mapping={"user_id": "1", "username": "Renamed"})
    await asyncio.gather(game.repo.pay(rid), other.pay(rid))
    assert await game.redis.hget("player:1:user_stats", "gold") == "9999"
    winner = json.loads(await game.redis.get(LAST_WINNER))
    assert winner["user"] == 1
    assert winner["name"] == "Renamed"
    assert frozen["number"] == (await game.redis.hgetall(round_key(rid)))["number"]
    await game.repo.retire(rid)
    await game.repo.advance()
    assert json.loads(await game.redis.get(LAST_WINNER)) == winner


@pytest.mark.asyncio
async def test_capacity_pending_does_not_erase_previous_winner_and_is_devalued(game):
    """No trunca ni resortea; mantiene saldo reclamable hasta liberar capacidad."""
    previous = encode({"name": "Previous", "prize": 12, "round": "previous"})
    await game.redis.set(LAST_WINNER, previous)
    await bet(game)
    rid = await game.repo.current()
    game.now[0] += 300
    await game.repo.close(rid)
    await game.redis.hset("player:1:user_stats", "gold", MAX_PLAYER_GOLD)
    await game.redis.set("bank:1:gold", MAX_BANK_GOLD)
    assert not (await game.repo.pay(rid))["applied"]
    assert await game.redis.get(LAST_WINNER) == previous
    game.now[0] += 86400
    await game.repo.refresh(rid)
    await game.redis.hset("player:1:user_stats", "gold", MAX_PLAYER_GOLD - 200)
    paid = await game.repo.pay(rid)
    assert paid["applied"]
    assert paid["prize"] == 99
    # 99 * 1% deja fracción; el siguiente día la acumula en vez de imponer mínimo.
    assert await game.redis.get("lottery:tax_remainder") == "9900"


@pytest.mark.asyncio
async def test_devaluation_exact_allocation_and_no_double_charge(game):
    """La reserva se liquida también tras días apagado y conserva cada moneda."""
    await bet(game)
    await bet(game, user=2, gross=300)
    rid = await game.repo.current()
    game.now[0] += 86400
    await game.repo.refresh(rid)
    await game.repo.refresh(rid)
    rows = {
        uid: json.loads(v) for uid, v in (await game.redis.hgetall(participants_key(rid))).items()
    }
    state = await game.redis.hgetall(round_key(rid))
    assert sum(row["net"] for row in rows.values()) == int(state["pool"]) == 393
    assert int(state["devalued"]) == 3
    assert rows["1"]["net"] == 98
    assert rows["2"]["net"] == 295
    assert int(state["gross"]) == int(state["fees"]) + int(state["pool"]) + int(state["devalued"])


@pytest.mark.asyncio
async def test_cancel_refunds_entire_gross_once_and_preserves_winner(game):
    """Comisión reservada vuelve al jugador; cancelar no anuncia ganador."""
    await game.redis.set(LAST_WINNER, "historical")
    await bet(game)
    await bet(game, user=2, gross=300)
    rid = await game.repo.current()
    await game.repo.cancel(rid, "Prueba de devolución")
    assert not (await bet(game))["applied"]
    for _ in range(4):
        await game.repo.refund(rid)
    assert await game.redis.hget(round_key(rid), "status") == "cancelled"
    assert await game.redis.get(LAST_WINNER) == "historical"
    for user in (1, 2):
        assert await game.redis.hget(f"player:{user}:user_stats", "gold") == "10000"


@pytest.mark.asyncio
async def test_concurrent_bet_bank_and_replays_conserve_gold(game):
    """Una transferencia bancaria competidora observa los mismos recursos de saldo."""
    rid = await game.repo.current()
    identity = operation_id()

    def transfer(snapshot):
        gold = int(snapshot["player:1:user_stats"]["gold"])
        bank = int(snapshot["bank:1:gold"] or 0)
        return Decision(
            {}, {"player:1:user_stats": {"gold": str(gold - 400)}, "bank:1:gold": str(bank + 400)}
        )

    results = await asyncio.gather(
        *(bet(game, identity=identity, round_id=rid) for _ in range(4)),
        transact(
            game.redis,
            (Resource("player:1:user_stats", "hash"), Resource("bank:1:gold", "string")),
            operation_id(),
            {"bank_test": 1},
            transfer,
        ),
    )
    assert all(row["applied"] for row in results[:4])
    assert await game.redis.hget("player:1:user_stats", "gold") == "9500"
    assert await game.redis.get("bank:1:gold") == "400"


@pytest.mark.asyncio
async def test_uncertain_fsync_after_exec_recovers_bet_and_payment(game):
    """Fallo después de EXEC no elimina ni duplica dinero en el reintento."""
    rid = await game.repo.current()
    identity = operation_id()
    with (
        patch(
            "src.services.lottery.repository.require_durable",
            AsyncMock(side_effect=RuntimeError("fsync unavailable")),
        ),
        pytest.raises(RuntimeError, match="fsync"),
    ):
        await bet(game, identity=identity, round_id=rid)
    assert (await bet(game, identity=identity, round_id=rid))["applied"]
    assert await game.redis.hget("player:1:user_stats", "gold") == "9900"
    game.now[0] += 300
    await game.repo.close(rid)
    with (
        patch(
            "src.services.lottery.repository.require_durable",
            AsyncMock(side_effect=RuntimeError("fsync unavailable")),
        ),
        pytest.raises(RuntimeError, match="fsync"),
    ):
        await game.repo.pay(rid)
    await game.repo.advance()
    assert await game.redis.hget("player:1:user_stats", "gold") == "9999"
    assert json.loads(await game.redis.get(LAST_WINNER))["prize"] == 99


@pytest.mark.asyncio
async def test_aof_crash_recovers_open_round_then_paid_result(game):
    """SIGKILL de Redis conserva recibos fsync y permite reanudar sorteo/pago."""
    if game.sandbox is None:
        pytest.skip("Requiere PYAO_RUN_LOTTERY_REDIS=1")
    await bet(game)
    rid = await game.repo.current()
    for stage in ("open", "paid"):
        await game.client.disconnect()
        await asyncio.to_thread(docker, "kill", "--signal", "KILL", game.sandbox.name)
        await asyncio.to_thread(docker, "start", game.sandbox.name)
        with game.sandbox.client() as sync:
            assert sync.ping()
        await game.client.connect(
            RedisConfig(
                host="127.0.0.1", port=game.sandbox.port, password_file=game.sandbox.password_file
            ),
            seed_defaults=False,
        )
        game.redis = game.client.redis
        game.repo = LotteryRepository(game.redis, clock=lambda: game.now[0])
        if stage == "open":
            assert await game.redis.hget(round_key(rid), "status") == "open"
            game.now[0] += 300
        await game.repo.advance()
        assert await game.redis.hget("player:1:user_stats", "gold") == "9999"
        assert json.loads(await game.redis.get(LAST_WINNER))["prize"] == 99


def test_interval_edges_and_proportional_rounding():
    """Fronteras documentadas, incluyendo intervalos vacíos de peso cero."""
    rows = {"1": {"net": 99}, "2": {"net": 297}, "3": {"net": 0}}
    assert [choose(rows, number) for number in (0, 98, 99, 395)] == [1, 1, 2, 2]
    for number in (-1, 396):
        with pytest.raises(ValueError, match="Boleto fuera"):
            choose(rows, number)
    assert proportional({"2": 1, "1": 1}, 1) == {"2": 0, "1": 1}


def test_production_draw_reproducible_commitment_and_probabilities():
    """Semillas CSPRNG en producción; fixture fija evalúa pesos con incertidumbre."""
    rng = random.Random(576)
    count = 20000
    wins = 0
    for _ in range(count):
        seed = rng.getrandbits(256).to_bytes(32, "big").hex()
        assert commitment(seed) == hashlib.sha256(bytes.fromhex(seed)).hexdigest()
        number = draw(seed, "1" * 32, "2" * 64, 396)
        wins += number < 99
    assert (
        abs(wins / count - 0.25) < 0.02
    )  # >6 sigma; evidencia reproducible, no prueba criptográfica.
    assert draw("00" * 32, "1" * 32, "2" * 64, 396) == draw("00" * 32, "1" * 32, "2" * 64, 396)


@pytest.mark.asyncio
async def test_scoped_hash_fields_never_read_all_or_write_outside_scope(game):
    """El recurso parcial usa HMGET y rechaza escrituras fuera del contrato."""
    with pytest.raises(ValueError, match="campos declarados"):
        await transact(
            game.redis,
            (Resource("hash:partial", "hash", fields=("1",)),),
            operation_id(),
            {},
            lambda _s: Decision({}, {"hash:partial": {"2": "not allowed"}}),
        )


@pytest.mark.asyncio
async def test_payment_uses_bank_without_truncating_or_erasing_prize(game):
    """El exceso del bolsillo llega al banco en el mismo commit que last_winner."""
    await bet(game)
    rid = await game.repo.current()
    game.now[0] += 300
    await game.repo.close(rid)
    await game.redis.hset("player:1:user_stats", "gold", MAX_PLAYER_GOLD - 20)
    result = await game.repo.pay(rid)
    assert result["applied"]
    assert result["prize"] == 99
    assert await game.redis.hget("player:1:user_stats", "gold") == str(MAX_PLAYER_GOLD)
    assert await game.redis.get("bank:1:gold") == "79"


@pytest.mark.asyncio
async def test_lost_exec_reply_is_resolved_from_same_receipt(game, monkeypatch):
    """La respuesta del EXEC se pierde después de aplicarse, no antes del commit."""
    from redis.exceptions import ConnectionError as LostReply  # ruff: ignore[import-outside-top-level]

    rid = await game.repo.current()
    pipeline_type = type(game.redis.pipeline())
    original = pipeline_type.execute
    lost = [False]

    async def execute(pipe, *args: object, **kwargs: object):
        result = await original(pipe, *args, **kwargs)
        if not lost[0]:
            lost[0] = True
            message = "Simulated lost EXEC reply"
            raise LostReply(message)
        return result

    monkeypatch.setattr(pipeline_type, "execute", execute)
    result = await bet(game, round_id=rid)
    assert lost[0]
    assert result["applied"]
    assert await game.redis.hget("player:1:user_stats", "gold") == "9900"


@pytest.mark.asyncio
async def test_position_changed_during_watch_rejects_without_debit(game, monkeypatch):
    """Un movimiento concurrente invalida el snapshot, incluso tras la prelectura."""
    from src.utils import resource_transaction  # ruff: ignore[import-outside-top-level]

    rid = await game.repo.current()
    original = resource_transaction._read_snapshot
    moved = [False]

    async def read_snapshot(pipe, resources):
        snapshot = await original(pipe, resources)
        if not moved[0]:
            moved[0] = True
            await game.redis.hset("player:1:position", "map", "2")
        return snapshot

    monkeypatch.setattr(resource_transaction, "_read_snapshot", read_snapshot)
    assert not (await bet(game, round_id=rid))["applied"]
    assert await game.redis.hget("player:1:user_stats", "gold") == "10000"


def test_rng_rejects_biased_tail_before_using_next_counter(monkeypatch):
    """No utiliza módulo sobre el bloque rechazado del HMAC."""
    from src.services.lottery import rules  # ruff: ignore[import-outside-top-level]

    blocks = iter([(2**256 - 1).to_bytes(32, "big"), (98).to_bytes(32, "big")])
    counters = []

    def digest(_key, message, _algorithm):
        counters.append(int.from_bytes(message[-8:], "big"))
        return next(blocks)

    monkeypatch.setattr(rules.hmac, "digest", digest)
    assert draw("00" * 32, "1" * 32, "2" * 64, 396) == 98
    assert counters == [0, 1]


@pytest.mark.asyncio
async def test_depleted_pool_does_not_announce_zero_prize_winner(game):
    """Al desaparecer todo el pozo, termina sin reemplazar al ganador histórico."""
    await game.redis.set(LAST_WINNER, "historical")
    await bet(game)
    rid = await game.repo.current()
    game.now[0] += 300
    await game.redis.hset(round_key(rid), mapping={"pool": "0", "devalued": "99"})
    await game.redis.hset(participants_key(rid), "1", encode({"gross": 100, "fee": 1, "net": 0}))
    await game.repo.advance()
    assert await game.redis.get(LAST_WINNER) == "historical"
    assert await game.redis.hget(round_key(rid), "status") == "cancelled"
