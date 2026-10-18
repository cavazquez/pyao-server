"""Aprender/reordenar compiten sobre el mismo libro sin destruir objetos."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from redis.exceptions import ConnectionError as RedisConnectionError

from src.repositories.spellbook_repository import SpellbookRepository
from src.services.scroll_learning import ScrollRule, learn_scroll
from src.utils.gold_atomic import operation_id
from src.utils.redis_config import RedisKeys


@pytest_asyncio.fixture
async def scroll_user(redis_client):
    """Personaje sintético habilitado y dos unidades de un pergamino del catálogo propio."""
    await redis_client.hset(
        RedisKeys.account_data("usr"), mapping={"user_id": "1", "char_class": "1"}
    )
    await redis_client.hset(RedisKeys.player_inventory(1), mapping={"slot_30": "197:2"})
    await redis_client.hset(RedisKeys.player_user_stats(1), mapping={"min_hp": "100", "level": "5"})
    await redis_client.hset(RedisKeys.player_skills(1), mapping={"level:magia": "20"})
    return redis_client.redis


def rule(**changes: object):
    """Política mínima explícita del pergamino de Flecha Mágica."""
    return ScrollRule(
        **(
            {
                "item_id": 197,
                "spell_id": 6,
                "minimum_level": 1,
                "minimum_magic": 12,
                "allowed_classes": (1, 2, 3),
            }
            | changes
        )
    )


@pytest.mark.asyncio
async def test_concurrent_learning_and_replay_once(scroll_user, redis_client):
    """Dos operaciones no aprenden ni gastan dos unidades; replay conserva ambos saldos."""
    identities = [operation_id(), operation_id()]
    with patch("src.services.scroll_learning.require_durable", new=AsyncMock()):
        results = await asyncio.gather(
            *(learn_scroll(scroll_user, 1, "usr", 30, identity, rule()) for identity in identities)
        )
        assert sum(result["applied"] for result in results) == 1
        winner = identities[
            next(index for index, result in enumerate(results) if result["applied"])
        ]
        assert (await learn_scroll(scroll_user, 1, "usr", 30, winner, rule()))["applied"]
    assert await redis_client.hget(RedisKeys.player_inventory(1), "slot_30") == "197:1"
    assert await SpellbookRepository(redis_client).get_all_spells(1) == {1: 6}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changes",
    [{"minimum_level": 10}, {"minimum_magic": 21}, {"allowed_classes": (12,)}, {"item_id": 199}],
)
async def test_invalid_requirements_do_not_consume(scroll_user, redis_client, changes):
    """Clase, nivel, magia y objeto se validan dentro del commit."""
    before = await redis_client.hgetall(RedisKeys.player_inventory(1))
    with patch("src.services.scroll_learning.require_durable", new=AsyncMock()):
        assert not (await learn_scroll(scroll_user, 1, "usr", 30, operation_id(), rule(**changes)))[
            "applied"
        ]
    assert await redis_client.hgetall(RedisKeys.player_inventory(1)) == before
    assert not await redis_client.hgetall(RedisKeys.player_spellbook(1))


@pytest.mark.asyncio
async def test_full_book_preserves_scroll_and_order(scroll_user, redis_client):
    """Sin hueco no se cambia el orden ni se consume; un hueco posterior sí se respeta."""
    book = {str(slot): "2" for slot in range(1, 36)}
    await redis_client.hset(RedisKeys.player_spellbook(1), mapping=book)
    with patch("src.services.scroll_learning.require_durable", new=AsyncMock()):
        assert not (await learn_scroll(scroll_user, 1, "usr", 30, operation_id(), rule()))[
            "applied"
        ]
        assert await redis_client.hgetall(RedisKeys.player_spellbook(1)) == book
        await redis_client.hdel(RedisKeys.player_spellbook(1), "27")
        assert (await learn_scroll(scroll_user, 1, "usr", 30, operation_id(), rule()))[
            "book_slot"
        ] == 27
    assert (await SpellbookRepository(redis_client).get_all_spells(1))[1] == 2


@pytest.mark.asyncio
async def test_learning_races_reorder_without_loss(scroll_user, redis_client):
    """WATCH evita que MOVE_SPELL sobrescriba un aprendizaje concurrente."""
    await redis_client.hset(RedisKeys.player_spellbook(1), mapping={"1": "2", "2": "3"})
    repo = SpellbookRepository(redis_client)
    with patch("src.services.scroll_learning.require_durable", new=AsyncMock()):
        await asyncio.gather(
            learn_scroll(scroll_user, 1, "usr", 30, operation_id(), rule()),
            repo.move_spell(1, 1, upwards=False),
        )
    assert await repo.get_all_spells(1) == {1: 3, 2: 2, 3: 6}


@pytest.mark.asyncio
async def test_lost_exec_ack_replay_does_not_consume_again(scroll_user, redis_client, monkeypatch):
    """Perder el ACK de EXEC conserva el recibo y nunca vuelve a retirar el ítem."""
    pipeline_type = type(scroll_user.pipeline())
    original = pipeline_type.execute
    lost = False

    async def execute(self, *args: object, **kwargs: object):
        nonlocal lost
        result = await original(self, *args, **kwargs)
        if not lost:
            lost = True
            message = "synthetic lost ACK"
            raise RedisConnectionError(message)
        return result

    monkeypatch.setattr(pipeline_type, "execute", execute)
    with patch("src.services.scroll_learning.require_durable", new=AsyncMock()):
        assert (await learn_scroll(scroll_user, 1, "usr", 30, operation_id(), rule()))["applied"]
    assert await redis_client.hget(RedisKeys.player_inventory(1), "slot_30") == "197:1"
