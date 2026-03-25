import os
import time
from collections import defaultdict, deque
from threading import Lock
from uuid import UUID

from fastapi import HTTPException, status


class InMemoryRateLimiter:
    def __init__(self):
        self._lock = Lock()
        self._events = defaultdict(deque)

    def check(self, key: str, limit: int, window_seconds: int) -> None:
        now = time.time()
        cutoff = now - window_seconds

        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please retry in a moment.",
                )

            bucket.append(now)


_wishlist_toggle_limiter = InMemoryRateLimiter()


def enforce_wishlist_toggle_rate_limit(user_id: UUID) -> None:
    limit = int(os.getenv("WISHLIST_TOGGLE_RATE_LIMIT", "30"))
    window_seconds = int(os.getenv("WISHLIST_TOGGLE_RATE_WINDOW_SECONDS", "60"))
    _wishlist_toggle_limiter.check(
        key=f"wishlist:toggle:{user_id}",
        limit=limit,
        window_seconds=window_seconds,
    )
