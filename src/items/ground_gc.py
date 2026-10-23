"""Retiro acotado de metadatos cuyo suelo ya desapareció por TTL."""

import time
from typing import TYPE_CHECKING, cast

from src.utils.ground_state import GROUND_TTL_SECONDS

if TYPE_CHECKING:
    from redis.asyncio import Redis
    from redis.asyncio.client import Pipeline

QUEUE_KEY = "items:ground:gc"
RETIRED_TTL_SECONDS = 604800
BATCH_SIZE = 64
_COLLECT = """
local now = math.max(tonumber(ARGV[1]), tonumber(redis.call('GET', KEYS[2]) or '0'))
local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', now, 'LIMIT', 0, ARGV[2])
local tiles, retired = {}, 0
for _,iid in ipairs(ids) do
    local key = 'item:instance:' .. iid
    local location = redis.call('HGET', key, 'location') or ''
    local ground,field,stack = string.match(location, '^(ground_items:%d+)|([^/]+)/(.+)$')
    if ground then
        local tilekey = ground .. '|' .. field
        if tiles[tilekey] == nil then
            local raw = redis.call('HGET', ground, field)
            local ok, tile = true, {}
            if raw then ok, tile = pcall(cjson.decode, raw) end
            if not ok or type(tile) ~= 'table' or (raw and not string.match(raw, '^%s*%[')) then
                tiles[tilekey] = false
            else
                local refs = {}
                for _,item in ipairs(tile) do
                    if type(item) ~= 'table' or type(item.stack_id) ~= 'string' or
                        (item.instance_ids and type(item.instance_ids) ~= 'table') then
                        refs = false
                        break
                    elseif type(item.instance_ids) == 'table' then
                        local members = {}
                        for _,id in ipairs(item.instance_ids) do members[id] = true end
                        refs[item.stack_id or ''] = members
                    end
                end
                tiles[tilekey] = refs
            end
        end
        local tile = tiles[tilekey]
        if tile == false or (tile[stack] and tile[stack][iid]) then
            -- Un depósito posterior puede haber renovado el TTL del mapa.
            redis.call('ZADD', KEYS[1], now + tonumber(ARGV[3]), iid)
        else
            redis.call('HSET', key, 'location', 'retired', 'last_seen', now)
            redis.call('HINCRBY', key, 'version', 1)
            redis.call('EXPIRE', key, ARGV[4])
            redis.call('ZREM', KEYS[1], iid)
            retired = retired + 1
        end
    else
        redis.call('ZREM', KEYS[1], iid)
    end
end
return {#ids, retired}
"""


def enqueue(pipe: Pipeline, key: str, state: dict[str, str]) -> None:
    """Actualiza el índice derivado dentro del mismo EXEC que mueve el objeto."""
    iid = key.removeprefix("item:instance:")
    if state.get("location", "").startswith("ground_items:"):
        pipe.zadd(QUEUE_KEY, {iid: int(state["last_seen"]) + GROUND_TTL_SECONDS})
    else:
        pipe.zrem(QUEUE_KEY, iid)


async def collect(redis: Redis, *, now: int | None = None) -> tuple[int, int]:
    """Revisa hasta 64 vencimientos y conserva toda referencia todavía existente.

    Returns:
        Cantidades examinada y retirada; nunca recorre todos los objetos.
    """
    result = cast(
        "list[int]",
        await redis.eval(
            _COLLECT,
            2,
            QUEUE_KEY,
            "items:clock",
            int(time.time()) if now is None else now,
            BATCH_SIZE,
            GROUND_TTL_SECONDS,
            RETIRED_TTL_SECONDS,
        ),
    )
    return result[0], result[1]
