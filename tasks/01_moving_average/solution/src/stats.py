"""Small statistics helpers."""


def moving_average(values, k):
    """Return the mean of each window of k consecutive values."""
    if k <= 0:
        raise ValueError("k must be a positive integer")
    if k > len(values):
        raise ValueError("k cannot be larger than the number of values")

    averages = []
    for start in range(len(values) - k + 1):
        window = values[start : start + k]
        averages.append(sum(window) / k)
    return averages
