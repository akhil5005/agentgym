from src.limiter import RateLimiter

import pytest


def test_a_burst_up_to_the_limit_is_allowed():
    limiter = RateLimiter(limit=5, window_seconds=60)
    for second in range(5):
        assert limiter.allow("alice", second) is True


def test_the_request_past_the_limit_is_denied():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 1) is True
    assert limiter.allow("alice", 2) is False


def test_a_denied_request_is_not_recorded():
    # Being denied must not push the oldest request out of the window, or a
    # blocked caller could keep itself blocked forever.
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 5) is False
    assert limiter.allow("alice", 10) is True


def test_two_keys_do_not_share_an_allowance():
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("bob", 0) is True
    assert limiter.allow("alice", 1) is False
    assert limiter.allow("bob", 1) is False


def test_one_key_exhausting_its_limit_does_not_block_another():
    limiter = RateLimiter(limit=3, window_seconds=60)
    for second in range(3):
        assert limiter.allow("noisy", second) is True
    assert limiter.allow("noisy", 4) is False
    assert limiter.allow("quiet", 4) is True


def test_many_keys_stay_independent():
    limiter = RateLimiter(limit=2, window_seconds=60)
    keys = [f"user-{index}" for index in range(25)]
    for key in keys:
        assert limiter.allow(key, 0) is True
        assert limiter.allow(key, 1) is True
    for key in keys:
        assert limiter.allow(key, 2) is False


def test_interleaved_keys_keep_separate_counts():
    limiter = RateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("a", 0) is True
    assert limiter.allow("b", 0) is True
    assert limiter.allow("a", 1) is True
    assert limiter.allow("b", 1) is True
    assert limiter.allow("a", 2) is False
    assert limiter.allow("b", 2) is False


def test_a_request_exactly_one_window_old_has_left_the_window():
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 10) is True


def test_just_inside_the_window_still_counts():
    limiter = RateLimiter(limit=1, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 9.999) is False


def test_the_window_slides_one_request_at_a_time():
    limiter = RateLimiter(limit=2, window_seconds=10)
    assert limiter.allow("alice", 0) is True
    assert limiter.allow("alice", 5) is True
    assert limiter.allow("alice", 9) is False
    # At t=10 the request from t=0 has expired, freeing exactly one slot.
    assert limiter.allow("alice", 10) is True
    assert limiter.allow("alice", 11) is False


def test_the_allowance_recovers_after_a_full_window():
    limiter = RateLimiter(limit=3, window_seconds=10)
    for second in (0, 1, 2):
        assert limiter.allow("alice", second) is True
    assert limiter.allow("alice", 3) is False
    for second in (20, 21, 22):
        assert limiter.allow("alice", second) is True


def test_bad_constructor_arguments_raise():
    for limit, window in ((0, 10), (-1, 10), (3, 0), (3, -5)):
        with pytest.raises(ValueError):
            RateLimiter(limit=limit, window_seconds=window)
