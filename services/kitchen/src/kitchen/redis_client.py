from functools import lru_cache

import redis

from kitchen import settings


@lru_cache(maxsize=1)
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.REDIS_URL)
