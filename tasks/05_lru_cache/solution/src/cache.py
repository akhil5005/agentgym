"""A fixed-size cache that forgets the least recently used entry."""


class LRUCache:
    """Holds at most `capacity` entries."""

    def __init__(self, capacity):
        if capacity <= 0:
            raise ValueError("capacity must be a positive integer")
        self.capacity = capacity
        self._values = {}
        self._order = []  # least recently used first

    def _mark_as_recent(self, key):
        """Move a key to the recent end of the order list."""
        self._order.remove(key)
        self._order.append(key)

    def get(self, key, default=None):
        if key not in self._values:
            return default
        # A successful read is a use, so it changes who gets evicted next.
        self._mark_as_recent(key)
        return self._values[key]

    def put(self, key, value):
        if key in self._values:
            self._values[key] = value
            # Replacing a value is a use too.
            self._mark_as_recent(key)
            return

        if len(self._values) >= self.capacity:
            oldest = self._order.pop(0)
            del self._values[oldest]

        self._values[key] = value
        self._order.append(key)

    def __len__(self):
        return len(self._values)
