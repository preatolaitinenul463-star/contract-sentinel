"""Redis-backed cache for search results and fetched page content.

Falls back to in-memory LRU cache when Redis is unavailable.
TTL defaults to 15 minutes for search, 60 minutes for fetched pages.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from typing import Any, Optional

from loguru import logger

from app.config import settings

# ── In-memory fallback ──

_mem_cache: OrderedDict[str, tuple[float, Any]] = OrderedDict()
_MEM_MAX = 200


def _mem_get(key: str, ttl: float) -> Optional[Any]:
    if key in _mem_cache:
        ts, val = _mem_cache[key]
        if time.time() - ts < ttl:
            _mem_cache.move_to_end(key)
            return val
        else:
            del _mem_cache[key]
    return None


def _mem_set(key: str, val: Any):
    _mem_cache[key] = (time.time(), val)
    if len(_mem_cache) > _MEM_MAX:
        _mem_cache.popitem(last=False)


# ── Redis helpers ──

async def _get_redis():
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        return r
    except Exception:
        return None


# ── Public API ──

async def cache_get(namespace: str, query: str, ttl: float = 900) -> Optional[Any]:
    """Get a cached value by (namespace, query). Returns None on miss."""
    key = f"sentinel:{namespace}:{hashlib.md5(query.encode()).hexdigest()}"

    # Try Redis first
    redis = await _get_redis()
    if redis:
        try:
            raw = await redis.get(key)
            await redis.close()
            if raw:
                return json.loads(raw)
        except Exception:
            pass

    # Fallback to memory
    return _mem_get(key, ttl)


async def cache_set(namespace: str, query: str, value: Any, ttl: int = 900):
    """Store a value in cache with TTL (seconds)."""
    key = f"sentinel:{namespace}:{hashlib.md5(query.encode()).hexdigest()}"

    # Try Redis
    redis = await _get_redis()
    if redis:
        try:
            await redis.set(key, json.dumps(value, ensure_ascii=False, default=str), ex=ttl)
            await redis.close()
        except Exception:
            pass

    # Always write to memory as fallback
    _mem_set(key, value)
