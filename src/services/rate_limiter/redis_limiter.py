import uuid

import redis

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
        self._allow_request_script = client.register_script(_ALLOW_REQUEST_SCRIPT)

    def allow_request(self, timestamp: float) -> bool:
        # Member must be unique: identical timestamps would otherwise collapse into one entry.
        member = f"{timestamp}:{uuid.uuid4().hex}"
        result = self._allow_request_script(
            keys=[self.key],
            args=[timestamp, self.window_seconds, self.max_requests, member],
        )
        return bool(result)
