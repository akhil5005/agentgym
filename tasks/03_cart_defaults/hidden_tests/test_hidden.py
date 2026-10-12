from src.cart import Cart


def test_new_cart_starts_empty():
    assert Cart().items == []
    assert Cart().total() == 0


def test_two_carts_stay_independent():
    first = Cart()
    second = Cart()
    first.add("book", 10.0)
    assert second.items == []
    assert second.total() == 0


def test_three_carts_stay_independent():
    carts = [Cart(), Cart(), Cart()]
    carts[1].add("pen", 2.5)
    assert len(carts[0].items) == 0
    assert len(carts[1].items) == 1
    assert len(carts[2].items) == 0


def test_each_item_owns_its_tags():
    cart = Cart()
    cart.add("book", 10.0)
    cart.add("pen", 2.5)
    cart.items[0]["tags"].append("gift")
    assert cart.items[0]["tags"] == ["gift"]
    assert cart.items[1]["tags"] == []


def test_supplied_tags_are_copied_not_aliased():
    cart = Cart()
    tags = ["sale"]
    cart.add("book", 10.0, tags)
    tags.append("clearance")
    assert cart.items[0]["tags"] == ["sale"]


def test_cart_built_from_a_list_copies_it():
    items = [{"name": "book", "price": 10.0, "tags": []}]
    cart = Cart(items)
    items.append({"name": "pen", "price": 2.5, "tags": []})
    assert len(cart.items) == 1


def test_total_sums_prices():
    cart = Cart()
    for name, price in (("a", 1.0), ("b", 2.0), ("c", 3.5)):
        cart.add(name, price)
    assert cart.total() == 6.5


def test_remove_existing_item():
    cart = Cart()
    cart.add("book", 10.0)
    cart.add("pen", 2.5)
    assert cart.remove("book") is True
    assert [item["name"] for item in cart.items] == ["pen"]
    assert cart.total() == 2.5


def test_remove_missing_item_returns_false():
    cart = Cart()
    cart.add("book", 10.0)
    assert cart.remove("nothing") is False
    assert len(cart.items) == 1


def test_remove_only_deletes_the_first_match():
    cart = Cart()
    cart.add("book", 10.0)
    cart.add("book", 10.0)
    assert cart.remove("book") is True
    assert len(cart.items) == 1
