"""Interval arithmetic."""


def merge_intervals(intervals):
    """Collapse overlapping intervals into the smallest covering set."""
    if not intervals:
        return []

    for start, end in intervals:
        if start > end:
            raise ValueError(f"interval start {start} is after its end {end}")

    merged = [list(intervals[0])]
    for start, end in intervals[1:]:
        last = merged[-1]
        if start < last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return merged
