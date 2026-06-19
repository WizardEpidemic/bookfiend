# Provides Redis-backed request rate limiting for expensive BookFiend API operations.

from fastapi import HTTPException, Request, status
from redis.exceptions import RedisError

from app.config import settings
from app.redis_client import redis_client


RATE_LIMIT_SCRIPT = """
local current = redis.call("INCR", KEYS[1])

if current == 1 then
    redis.call("EXPIRE", KEYS[1], ARGV[1])
end

local ttl = redis.call("TTL", KEYS[1])

return {current, ttl}
"""


def _client_identifier(request: Request) -> str:
    if request.client is None:
        return "unknown"

    return request.client.host


def enforce_scan_rate_limit(request: Request) -> None:
    client_id = _client_identifier(request)

    key = (
        "bookfiend:rate_limit:"
        f"scan:{client_id}"
    )

    try:
        current_count, ttl = redis_client.eval(
            RATE_LIMIT_SCRIPT,
            1,
            key,
            settings.scan_rate_window_seconds,
        )
    except RedisError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Rate limiting service is temporarily unavailable."
            ),
        ) from exc

    if int(current_count) <= settings.scan_rate_limit:
        return

    retry_after = max(
        int(ttl),
        1,
    )

    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=(
            "Too many bookshelf scan requests. "
            f"Try again in {retry_after} seconds."
        ),
        headers={
            "Retry-After": str(retry_after),
        },
    )