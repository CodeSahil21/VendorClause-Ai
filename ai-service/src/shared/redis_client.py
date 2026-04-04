# Standard library
import asyncio

# Third-party
from redis.asyncio import Redis

# Local
from src.shared.settings import settings


def create_redis_client() -> Redis:
    return Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        password=settings.redis_password,
        decode_responses=True,
    )


_redis_singleton: Redis | None = None
_redis_lock = asyncio.Lock()


async def get_shared_redis() -> Redis:
    global _redis_singleton
    if _redis_singleton is not None:
        return _redis_singleton

    async with _redis_lock:
        if _redis_singleton is None:
            _redis_singleton = create_redis_client()
    return _redis_singleton


async def close_shared_redis() -> None:
    global _redis_singleton
    if _redis_singleton is not None:
        await _redis_singleton.close()
        _redis_singleton = None
