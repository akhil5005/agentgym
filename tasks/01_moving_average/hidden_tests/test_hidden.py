from src.stats import moving_average

import pytest


def test_number_of_windows_is_n_minus_k_plus_one():
    values = [1, 2, 3, 4, 5, 6, 7]
    for k in (1, 2, 3, 7):
        assert len(moving_average(values, k)) == len(values) - k + 1


def test_exact_values_for_window_of_two():
    assert moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]


def test_exact_values_for_window_of_three():
    assert moving_average([2, 4, 6, 8, 10], 3) == [4.0, 6.0, 8.0]


def test_window_of_one_mirrors_the_input():
    assert moving_average([7, -3, 0], 1) == [7.0, -3.0, 0.0]


def test_full_width_window_returns_one_average():
    assert moving_average([1, 2, 3, 4], 4) == [2.5]


def test_single_value_with_window_of_one():
    assert moving_average([42], 1) == [42.0]


def test_floats_are_handled():
    result = moving_average([0.5, 1.5, 2.5], 2)
    assert result == pytest.approx([1.0, 2.0])


def test_zero_or_negative_window_raises():
    for bad_k in (0, -1, -5):
        with pytest.raises(ValueError):
            moving_average([1, 2, 3], bad_k)


def test_window_larger_than_input_raises():
    with pytest.raises(ValueError):
        moving_average([1, 2], 3)


def test_input_is_not_modified():
    values = [1, 2, 3, 4]
    moving_average(values, 2)
    assert values == [1, 2, 3, 4]
