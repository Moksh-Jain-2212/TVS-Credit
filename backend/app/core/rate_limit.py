"""In-memory rate limits for local/prototype abuse controls."""

from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from collections.abc import Callable

from fastapi import HTTPException, Request, status


BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def rate_limit(route_key: str, *, default_limit: int, window_seconds: int) -> Callable[[Request], None]:
    env_key = f"RATE_LIMIT_{route_key.upper()}_PER_WINDOW"
    limit = int(os.getenv(env_key, str(default_limit)))

    def dependency(request: Request) -> None:
        if os.getenv("DISABLE_RATE_LIMITS", "").lower() in {"1", "true", "yes"} or os.getenv("PYTEST_CURRENT_TEST"):
            return
        client = request.client.host if request.client else "unknown"
        key = f"{route_key}:{client}"
        now = time.monotonic()
        bucket = BUCKETS[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests. Please wait and retry.")
        bucket.append(now)

    return dependency
