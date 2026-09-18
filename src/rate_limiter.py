from collections import deque

MAX_REQUESTS = 10
WINDOW_SECONDS = 60


class RateLimiter:
    """Single-user, in-memory rate limiter. Multi-user tracking is a separate ticket."""

    def __init__(self, max_requests: int = MAX_REQUESTS, window_seconds: int = WINDOW_SECONDS) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._timestamps: deque[float] = deque()

    def _evict_expired(self, timestamp: float) -> None:
        while self._timestamps and timestamp - self._timestamps[0] >= self.window_seconds:
            self._timestamps.popleft()

    def allow_request(self, timestamp: float) -> bool:
        self._evict_expired(timestamp)
        if len(self._timestamps) >= self.max_requests:
            return False
        self._timestamps.append(timestamp)
        return True
