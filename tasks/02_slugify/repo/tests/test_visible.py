from src.text import slugify


def test_simple_title():
    assert slugify("Hello, World!") == "hello-world"


def test_already_a_slug_is_unchanged():
    assert slugify("already-clean") == "already-clean"


def test_surrounding_and_repeated_spaces():
    assert slugify("  Spaces   Everywhere  ") == "spaces-everywhere"
