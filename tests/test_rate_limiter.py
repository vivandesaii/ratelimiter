from src.rate_limiter import RateLimiter


def test_request_under_limit() -> None:
    limiter = RateLimiter(max_requests=10, window_seconds=60)

    for i in range(10):
        assert limiter.allow_request(timestamp=float(i)) is True


def test_request_over_limit() -> None:
    limiter = RateLimiter(max_requests=10, window_seconds=60)

    for i in range(10):
        assert limiter.allow_request(timestamp=float(i)) is True

    assert limiter.allow_request(timestamp=10.0) is False


def test_request_allowed_after_oldest_expires() -> None:
    limiter = RateLimiter(max_requests=10, window_seconds=60)

    for i in range(10):
        assert limiter.allow_request(timestamp=float(i)) is True

    # 11th request would be blocked, but the oldest timestamp (t=0) is now
    # exactly 60s old and should be evicted before the count is checked.
    assert limiter.allow_request(timestamp=60.0) is True

def test_rejected_request_leaves_no_phantom_entry() -> None:
    limiter = RateLimiter(max_requests=10, window_seconds=60)

    for i in range(10):
        assert limiter.allow_request(timestamp=float(i)) is True

    # 11th request should be rejected, and must NOT be added to the deque
    assert limiter.allow_request(timestamp=5.0) is False
    assert len(limiter._timestamps) == 10