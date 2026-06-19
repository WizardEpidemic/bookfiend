# Provides structured JSON logging helpers for BookFiend API and worker events.

import json
import logging
from datetime import datetime, timezone
from typing import Any


logger = logging.getLogger("bookfiend")


def log_event(
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    payload = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": logging.getLevelName(level).lower(),
        "event": event,
        **fields,
    }

    logger.log(
        level,
        json.dumps(
            payload,
            default=str,
            separators=(",", ":"),
        ),
    )