"""A very small shopping cart."""


class Cart:
    """Holds items, each of which has a name, a price and some tags."""

    def __init__(self, items=[]):
        self.items = items

    def add(self, name, price, tags=[]):
        self.items.append({"name": name, "price": price, "tags": tags})

    def remove(self, name):
        for item in self.items:
            if item["name"] == name:
                self.items.remove(item)
                return True
        return False

    def total(self):
        return sum(item["price"] for item in self.items)
