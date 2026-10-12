"""Rate limiting with a sliding window."""

from collections import deque


class RateLimiter:
    """Allows `limit` requests per key within any `window_seconds` window."""

    def __init__(self, limit, window_seconds):
        if limit <= 0:
            raise ValueError("limit must be a positive integer")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")

        self.limit = limit
        self.window_seconds = window_seconds
        # One queue of timestamps per key. A single shared queue would let a
        # noisy caller spend everyone else's allowance.
        self._events_by_key = {}

    def allow(self, key, now):
        events = self._events_by_key.setdefault(key, deque())

        # The window is half-open: a request made exactly window_seconds ago
        # has already left it, so the test is >= and not >.
        while events and now - events[0] >= self.window_seconds:
            events.popleft()

        if len(events) >= self.limit:
            return False

        events.append(now)
        return True
