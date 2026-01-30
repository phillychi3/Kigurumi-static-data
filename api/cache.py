from cachetools import TTLCache
from typing import Any, Optional


cache = TTLCache(maxsize=1000, ttl=86400)


def get_cache(key: str) -> Optional[Any]:
    return cache.get(key)


def set_cache(key: str, value: Any) -> None:
    cache[key] = value


def delete_cache(key: str) -> None:
    if key in cache:
        del cache[key]


def clear_cache() -> None:
    cache.clear()


def invalidate_cache_by_prefix(prefix: str) -> None:
    keys_to_delete = [key for key in cache.keys() if key.startswith(prefix)]
    for key in keys_to_delete:
        del cache[key]


def get_cache_stats() -> dict:
    return {
        "size": len(cache),
        "maxsize": cache.maxsize,
        "ttl": cache.ttl,
        "currsize": cache.currsize,
    }
