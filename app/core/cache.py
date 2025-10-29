import json
from typing import Any, Callable, Optional

import redis

from app.core.config import settings


_client: Optional[redis.Redis] = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.from_url(settings.redis_url, decode_responses=True)
    return _client


def cached_json(key: str, ttl_seconds: int, loader: Callable[[], Any]):
    r = get_redis()
    cached = r.get(key)
    if cached is not None:
        return json.loads(cached)
    data = loader()
    r.setex(key, ttl_seconds, json.dumps(data))
    return data


