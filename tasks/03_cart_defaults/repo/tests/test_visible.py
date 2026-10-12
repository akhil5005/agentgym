from src.cart import Cart


def test_add_and_total():
    cart = Cart()
    cart.add("book", 10.0)
    cart.add("pen", 2.5)
    assert cart.total() == 12.5


def test_two_carts_are_independent():
    first = Cart()
    second = Cart()
    first.add("book", 10.0)
    assert second.items == []


def test_each_item_owns_its_tags():
    cart = Cart()
    cart.add("book", 10.0)
    cart.add("pen", 2.5)
    cart.items[0]["tags"].append("gift")
    assert cart.items[1]["tags"] == []
