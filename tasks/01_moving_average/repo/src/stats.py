"""Small statistics helpers."""


def moving_average(values, k):
    """Return the mean of each window of k consecutive values."""
    if k <= 0:
        raise ValueError("k must be a positive integer")

    averages = []
    for start in range(len(values) - k):
        window = values[start : start + k]
        averages.append(sum(window) / k)
    return averages
