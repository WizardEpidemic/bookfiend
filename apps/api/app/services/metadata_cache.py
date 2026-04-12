# Caches Open Library metadata responses in Redis to reduce repeated external API requests.

import json
import re
from typing import Any

from app.redis_client import redis_client


CACHE_TTL_SECONDS = 60 * 60 * 24


def _cache_key(
    search_type: str,
    query: str,
) -> str:
    normalized_query = re.sub(
        r"[^a-z0-9]+",
        ":",
        query.lower(),
    ).strip(":")

    return (
        f"bookfiend:openlibrary:"
        f"{search_type}:{normalized_query}"
    )


def get_cached_metadata(
    search_type: str,
    query: str,
) -> list[dict[str, Any]] | None:
    cached_value = redis_client.get(
        _cache_key(
            search_type,
            query,
        )
    )

    if cached_value is None:
        return None

    return json.loads(cached_value)


def cache_metadata(
    search_type: str,
    query: str,
    documents: list[dict[str, Any]],
) -> None:
    redis_client.setex(
        _cache_key(
            search_type,
            query,
        ),
        CACHE_TTL_SECONDS,
        json.dumps(documents),
    )