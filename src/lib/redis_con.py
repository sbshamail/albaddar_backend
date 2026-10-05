import json
from typing import Any, Optional

import redis

from src.config import REDIS_URL

redis_client = redis.from_url(REDIS_URL, decode_responses=True)


def cache_get(hashkey: str, field: str) -> Optional[Any]:
    """Read one cached field out of a hash. None on miss OR if Redis is down —
    caching is best-effort, callers should always fall back to the DB."""
    try:
        raw = redis_client.hget(hashkey, field)
    except redis.RedisError:
        return None
    return json.loads(raw) if raw else None


def cache_set(hashkey: str, field: str, value: Any, ttl: Optional[int] = None) -> None:
    """Write one field into a hash. `ttl` (seconds) applies to the whole hash,
    not just this field — it's the safety net in case an invalidation call
    site gets missed; real invalidation should still come from clear_hash()."""
    try:
        redis_client.hset(hashkey, field, json.dumps(value, default=str))
        if ttl:
            redis_client.expire(hashkey, ttl)
    except redis.RedisError:
        pass


def clear_hash(hashkey: str) -> None:
    """Invalidate every cached field under this key in one shot.
    e.g. clear_hash(f"user_session:{user_id}") after that user's roles/shop/
    profile change, or clear_hash("products") after any product write."""
    try:
        redis_client.delete(hashkey)
    except redis.RedisError:
        pass
