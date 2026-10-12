from src.limiter import RateLimiter

import pytest


def test_requests_up_to_the_limit_are_allowed():
    limiter = RateLimiter(limit=3, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 1) is True
    assert limiter.allow("alice", 2) is True
    assert limiter.allow("alice", 3) is False


def test_each_key_has_its_own_allowance():
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("bob", 0) is True


def test_a_request_exactly_one_window_old_has_expired():
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 10) is True


def test_limit_must_be_positive():
    with pytest.raises(ValueError):
        RateLimiter(limit=0, window_seconds=10)
