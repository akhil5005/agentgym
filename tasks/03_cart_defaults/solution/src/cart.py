"""A very small shopping cart."""


class Cart:
    """Holds items, each of which has a name, a price and some tags."""

    # A default argument is evaluated once, when the function is defined, so a
    # mutable default such as [] is shared by every call. None plus a fresh list
    # inside the body gives each cart its own storage.
    def __init__(self, items=None):
        self.items = list(items) if items is not None else []

    def add(self, name, price, tags=None):
        self.items.append(
            {
                "name": name,
                "price": price,
                # Copy the caller's list so later changes to it cannot reach in.
                "tags": list(tags) if tags is not None else [],
            }
        )

    def remove(self, name):
        for item in self.items:
            if item["name"] == name:
                self.items.remove(item)
                return True
        return False

    def total(self):
        return sum(item["price"] for item in self.items)
