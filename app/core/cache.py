import json
from typing import Any, Callable, Optional

import redis
from redis.exceptions import RedisError

from app.core.config import settings


_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def cached_json(key: str, ttl_seconds: int, loader: Callable[[], Any]):
    r = get_redis()
    try:
        cached = r.get(key)
    except RedisError:
        cached = None
    if cached is not None:
        try:
            decoded = json.loads(cached)
            # Don't return cached None values (errors)
            if decoded is not None:
                return decoded
        except json.JSONDecodeError:
            pass
    data = loader()
    # Only cache non-None values (successful responses)
    if data is not None:
        try:
            r.setex(key, ttl_seconds, json.dumps(data))
        except RedisError:
            pass
    return data


