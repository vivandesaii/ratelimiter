import uuid

import redis

from src.services.rate_limiter.in_memory import InMemoryRateLimiter
from src.services.rate_limiter.interface import RateLimiterInterface

MAX_REQUESTS = 10
WINDOW_SECONDS = 60
DEFAULT_KEY = "rate_limiter"

# Atomic expire-check-add: evicts entries outside the window, then only adds
# the new timestamp if the remaining count is under the limit. Running this as
# a single EVAL means no other client's commands can interleave between steps.
_ALLOW_REQUEST_SCRIPT = """
local key = KEYS[1]
local timestamp = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]

redis.call("ZREMRANGEBYSCORE", key, "-inf", timestamp - window_seconds)

local count = redis.call("ZCARD", key)

if count >= max_requests then
    return 0
end

redis.call("ZADD", key, timestamp, member)
return 1
"""


class RedisRateLimiter(RateLimiterInterface):
    """Single-user rate limiter backed by a Redis ZSET (score = request timestamp).

    The expire-check-add sequence runs as a single Lua script via EVAL, so it is
    atomic with respect to other clients hitting the same key.

    If Redis is unreachable, behavior depends on `fail_open`:
    - fail_open=False: the request is denied (returns False).
    - fail_open=True: falls back to a per-instance InMemoryRateLimiter. Known
      limitation: this fallback is not shared across instances, so during a
      Redis outage a multi-instance deployment enforces the limit independently
      per instance (effectively up to N times the configured limit, where N is
      the instance count). Accepted trade-off: degraded protection beats none.
    """

    def __init__(
        self,
        client: redis.Redis,
        key: str = DEFAULT_KEY,
        max_requests: int = MAX_REQUESTS,
        window_seconds: int = WINDOW_SECONDS,
        fail_open: bool = True,
    ) -> None:
        self.client = client
        self.key = key
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.fail_open = fail_open
        self._allow_request_script = client.register_script(_ALLOW_REQUEST_SCRIPT)
        self._fallback: InMemoryRateLimiter | None = None

    def allow_request(self, timestamp: float) -> bool:
        # Member must be unique: identical timestamps would otherwise collapse into one entry.
        member = f"{timestamp}:{uuid.uuid4().hex}"
        try:
            result = self._allow_request_script(
                keys=[self.key],
                args=[timestamp, self.window_seconds, self.max_requests, member],
            )
        except (redis.ConnectionError, redis.TimeoutError):
            if not self.fail_open:
                return False
            if self._fallback is None:
                self._fallback = InMemoryRateLimiter(
                    max_requests=self.max_requests, window_seconds=self.window_seconds
                )
            return self._fallback.allow_request(timestamp)
        return bool(result)
