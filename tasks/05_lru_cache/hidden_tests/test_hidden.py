from src.cache import LRUCache

import pytest


def test_put_then_get_returns_the_value():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_a_missing_key_returns_the_default():
    cache = LRUCache(2)
    assert cache.get("nope") is None
    assert cache.get("nope", "fallback") == "fallback"


def test_length_tracks_the_contents():
    cache = LRUCache(2)
    assert len(cache) == 0
    cache.put("a", 1)
    assert len(cache) == 1
    cache.put("b", 2)
    cache.put("c", 3)
    assert len(cache) == 2


def test_the_least_recently_used_key_is_evicted():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    assert cache.get("a") is None


def test_a_successful_get_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 1
    assert cache.get("c") == 3


def test_a_get_refreshes_recency_with_a_larger_cache():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    cache.get("a")
    cache.put("d", 4)
    assert cache.get("b") is None
    assert cache.get("a") == 1


def test_repeated_gets_keep_a_key_alive_across_evictions():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.get("a")
    cache.put("c", 3)  # evicts "b"
    cache.get("a")
    cache.put("d", 4)  # evicts "c"
    assert cache.get("a") == 1
    assert cache.get("c") is None
    assert cache.get("d") == 4


def test_interleaved_gets_decide_the_eviction_order():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    cache.get("b")
    cache.get("a")
    cache.put("d", 4)  # "c" is now the least recently used
    assert cache.get("c") is None
    assert cache.get("a") == 1
    assert cache.get("b") == 2


def test_replacing_an_existing_value_refreshes_recency():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("a", 10)
    cache.put("c", 3)
    assert cache.get("b") is None
    assert cache.get("a") == 10


def test_replacing_a_value_refreshes_recency_with_a_larger_cache():
    cache = LRUCache(3)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)
    cache.put("a", 99)
    cache.put("d", 4)
    assert cache.get("b") is None
    assert cache.get("a") == 99
    assert len(cache) == 3


def test_replacing_a_value_does_not_grow_the_cache():
    cache = LRUCache(2)
    cache.put("a", 1)
    cache.put("a", 2)
    assert len(cache) == 1
    assert cache.get("a") == 2


def test_zero_or_negative_capacity_raises():
    for bad in (0, -1, -10):
        with pytest.raises(ValueError):
            LRUCache(bad)
