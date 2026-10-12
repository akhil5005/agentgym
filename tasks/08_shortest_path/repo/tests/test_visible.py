import math

from src.graph import shortest_path

import pytest


def test_single_edge():
    assert shortest_path({"A": {"B": 3}, "B": {}}, "A", "B") == (3, ["A", "B"])


def test_a_cheap_detour_beats_an_expensive_direct_edge():
    graph = {
        "A": {"B": 1, "C": 10},
        "B": {"C": 1},
        "C": {"D": 1},
        "D": {},
    }
    assert shortest_path(graph, "A", "D") == (3, ["A", "B", "C", "D"])


def test_diamond_picks_the_cheaper_branch():
    graph = {
        "A": {"B": 1, "C": 4},
        "B": {"D": 5},
        "C": {"D": 1},
        "D": {},
    }
    assert shortest_path(graph, "A", "D") == (5, ["A", "C", "D"])


def test_unreachable_goal():
    graph = {"A": {"B": 1}, "B": {}, "C": {}}
    assert shortest_path(graph, "A", "C") == (math.inf, [])
