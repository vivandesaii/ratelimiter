import os
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
import redis

from src.services.rate_limiter import RateLimiterInterface, RedisRateLimiter


@pytest.fixture
def client() -> Iterator[redis.Redis]:
    client = redis.Redis(host="localhost", port=6379)
    try:
        client.ping()
    except redis.ConnectionError:
        if os.environ.get("CI"):
            pytest.fail("Redis not reachable on localhost:6379 (required in CI)")
        pytest.skip("Redis not reachable on localhost:6379")
    yield client
    client.close()


@pytest.fixture
def limiter(client: redis.Redis) -> Iterator[RedisRateLimiter]:
    key = f"test:rate_limiter:{uuid.uuid4().hex}"
    yield RedisRateLimiter(client, key=key, max_requests=10, window_seconds=60)
    client.delete(key)


def test_implements_interface(limiter: RedisRateLimiter) -> None:
    assert isinstance(limiter, RateLimiterInterface)


def test_allows_requests_under_limit(limiter: RedisRateLimiter) -> None:
    for i in range(10):
        assert limiter.allow_request(timestamp=float(i)) is True


def test_rejects_request_at_limit(limiter: RedisRateLimiter) -> None:
    for i in range(10):
        assert limiter.allow_request(timestamp=float(i)) is True

    assert limiter.allow_request(timestamp=10.0) is False
    assert limiter.client.zcard(limiter.key) == 10


def test_concurrent_requests_never_exceed_limit(limiter: RedisRateLimiter) -> None:
    # Two "instances" share the same underlying key/client and both sit at a
    # count near the limit, then race to add one more each. Without the atomic
    # Lua script, both could read count=9 before either writes, landing at 11.
    for i in range(9):
        assert limiter.allow_request(timestamp=float(i)) is True

    other = RedisRateLimiter(
        limiter.client, key=limiter.key, max_requests=limiter.max_requests, window_seconds=limiter.window_seconds
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(limiter.allow_request, 9.0)
        future_b = executor.submit(other.allow_request, 9.0)
        results = [future_a.result(), future_b.result()]

    assert limiter.client.zcard(limiter.key) == limiter.max_requests
    assert sorted(results) == [False, True]
