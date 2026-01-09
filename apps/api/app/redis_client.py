from redis import Redis

from app.config import settings


redis_client = Redis.from_url(
    settings.redis_url,
    decode_responses=True,
)


def check_redis_connection() -> bool:
    return bool(redis_client.ping())