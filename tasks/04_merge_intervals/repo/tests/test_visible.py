from src.intervals import merge_intervals

import pytest


def test_overlapping_pair_merges():
    assert merge_intervals([[1, 3], [2, 5]]) == [[1, 5]]


def test_unsorted_input_is_handled():
    assert merge_intervals([[5, 7], [1, 3]]) == [[1, 3], [5, 7]]


def test_touching_intervals_merge():
    assert merge_intervals([[1, 2], [2, 3]]) == [[1, 3]]


def test_start_after_end_is_rejected():
    with pytest.raises(ValueError):
        merge_intervals([[5, 1]])
