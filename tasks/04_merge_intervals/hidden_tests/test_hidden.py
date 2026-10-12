from src.intervals import merge_intervals

import pytest


def test_empty_input():
    assert merge_intervals([]) == []


def test_single_interval():
    assert merge_intervals([[2, 4]]) == [[2, 4]]


def test_an_unsorted_pair_comes_back_in_order():
    assert merge_intervals([[5, 7], [1, 3]]) == [[1, 3], [5, 7]]


def test_an_unsorted_overlapping_pair_merges():
    assert merge_intervals([[3, 6], [1, 4]]) == [[1, 6]]


def test_reverse_sorted_input():
    assert merge_intervals([[7, 8], [4, 5], [1, 2]]) == [[1, 2], [4, 5], [7, 8]]


def test_completely_unsorted_input():
    assert merge_intervals([[8, 10], [1, 3], [15, 18], [2, 6]]) == [
        [1, 6],
        [8, 10],
        [15, 18],
    ]


def test_two_touching_intervals_become_one():
    assert merge_intervals([[1, 2], [2, 3]]) == [[1, 3]]


def test_a_chain_of_touching_intervals_becomes_one():
    assert merge_intervals([[1, 2], [2, 3], [3, 4]]) == [[1, 4]]


def test_touching_intervals_followed_by_a_gap():
    assert merge_intervals([[1, 2], [2, 3], [5, 6]]) == [[1, 3], [5, 6]]


def test_a_nested_interval_given_before_the_one_containing_it():
    assert merge_intervals([[3, 5], [1, 10]]) == [[1, 10]]


def test_start_after_end_raises():
    with pytest.raises(ValueError):
        merge_intervals([[1, 2], [9, 4]])


def test_input_is_not_modified():
    original = [[5, 7], [1, 3], [2, 6]]
    snapshot = [list(pair) for pair in original]
    merge_intervals(original)
    assert original == snapshot
