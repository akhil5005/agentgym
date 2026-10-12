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
        self._events = deque()

    def allow(self, key, now):
        while self._events and now - self._events[0] > self.window_seconds:
            self._events.popleft()

        if len(self._events) >= self.limit:
            return False

        self._events.append(now)
        return True
