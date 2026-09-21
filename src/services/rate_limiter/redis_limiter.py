import uuid

import redis

from src.services.rate_limiter.interface import RateLimiterInterface

MAX_REQUESTS = 10
WINDOW_SECONDS = 60
DEFAULT_KEY = "rate_limiter"


class RedisRateLimiter(RateLimiterInterface):
    """Single-user rate limiter backed by a Redis ZSET (score = request timestamp).

    Known gap: expire/check/add are three separate round-trips, so concurrent
    instances can briefly exceed the limit. Atomicity (Lua script) is a later ticket.
    """

    def __init__(
        self,
        client: redis.Redis,
        key: str = DEFAULT_KEY,
        max_requests: int = MAX_REQUESTS,
        window_seconds: int = WINDOW_SECONDS,
    ) -> None:
        self.client = client
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds

    def _evict_expired(self, timestamp: float) -> None:
        # Inclusive upper bound matches the in-memory `timestamp - oldest >= window`.
        self.client.zremrangebyscore(self.key, "-inf", timestamp - self.window_seconds)

    def allow_request(self, timestamp: float) -> bool:
        self._evict_expired(timestamp)
        if self.client.zcard(self.key) >= self.max_requests:
            return False
        # Member must be unique: identical timestamps would otherwise collapse into one entry.
        self.client.zadd(self.key, {f"{timestamp}:{uuid.uuid4().hex}": timestamp})
        return True
