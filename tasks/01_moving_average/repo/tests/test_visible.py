from src.stats import moving_average

import pytest


def test_window_of_two_over_three_values():
    assert moving_average([1, 2, 3], 2) == [1.5, 2.5]


def test_window_of_one_returns_each_value():
    assert moving_average([4, 5], 1) == [4.0, 5.0]


def test_zero_window_is_rejected():
    with pytest.raises(ValueError):
        moving_average([1, 2, 3], 0)
