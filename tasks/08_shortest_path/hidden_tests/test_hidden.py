import math

from src.graph import shortest_path

import pytest


def test_single_edge():
    assert shortest_path({"A": {"B": 3}, "B": {}}, "A", "B") == (3, ["A", "B"])


def test_start_equals_goal():
    assert shortest_path({"A": {"B": 1}, "B": {}}, "A", "A") == (0, ["A"])


def test_a_cheap_detour_beats_an_expensive_direct_edge():
    graph = {
        "A": {"B": 1, "C": 10},
        "B": {"C": 1},
        "C": {"D": 1},
        "D": {},
    }
    assert shortest_path(graph, "A", "D") == (3, ["A", "B", "C", "D"])


def test_two_hops_beat_one_expensive_hop():
    graph = {
        "S": {"X": 5, "Y": 1},
        "Y": {"X": 1},
        "X": {"T": 1},
        "T": {},
    }
    assert shortest_path(graph, "S", "T") == (3, ["S", "Y", "X", "T"])


def test_diamond_picks_the_cheaper_branch():
    graph = {
        "A": {"B": 1, "C": 4},
        "B": {"D": 5},
        "C": {"D": 1},
        "D": {},
    }
    assert shortest_path(graph, "A", "D") == (5, ["A", "C", "D"])


def test_a_long_chain_beats_one_expensive_shortcut():
    graph = {
        "A": {"B": 1, "E": 10},
        "B": {"C": 1},
        "C": {"D": 1},
        "D": {"E": 1},
        "E": {},
    }
    assert shortest_path(graph, "A", "E") == (4, ["A", "B", "C", "D", "E"])


def test_a_zero_cost_edge_can_be_part_of_the_best_route():
    graph = {
        "A": {"B": 2, "C": 1},
        "C": {"B": 0},
        "B": {"D": 1},
        "D": {},
    }
    assert shortest_path(graph, "A", "D") == (2, ["A", "C", "B", "D"])


def test_the_cheapest_route_can_revisit_a_better_predecessor():
    graph = {
        "S": {"A": 1, "B": 4},
        "A": {"B": 1, "G": 10},
        "B": {"G": 1},
        "G": {},
    }
    assert shortest_path(graph, "S", "G") == (3, ["S", "A", "B", "G"])


def test_all_zero_costs_give_a_zero_total():
    graph = {"A": {"B": 0}, "B": {"C": 0}, "C": {}}
    assert shortest_path(graph, "A", "C") == (0, ["A", "B", "C"])


def test_unreachable_goal_returns_infinity_and_no_path():
    graph = {"A": {"B": 1}, "B": {}, "C": {}}
    assert shortest_path(graph, "A", "C") == (math.inf, [])


def test_a_goal_that_is_not_in_the_graph_at_all():
    graph = {"A": {"B": 1}, "B": {}}
    assert shortest_path(graph, "A", "Z") == (math.inf, [])


def test_a_negative_edge_cost_raises():
    graph = {"A": {"B": -1}, "B": {}}
    with pytest.raises(ValueError):
        shortest_path(graph, "A", "B")
