"""Interval arithmetic."""


def merge_intervals(intervals):
    """Collapse overlapping intervals into the smallest covering set."""
    if not intervals:
        return []

    for start, end in intervals:
        if start > end:
            raise ValueError(f"interval start {start} is after its end {end}")

    # Sorting by start is what makes a single pass correct: once the list is
    # ordered, an interval can only ever overlap the one we merged last.
    ordered = sorted((list(pair) for pair in intervals), key=lambda pair: pair[0])

    merged = [ordered[0]]
    for start, end in ordered[1:]:
        last = merged[-1]
        # <= not <, because touching intervals such as [1,2] and [2,3] cover a
        # continuous range and must become one.
        if start <= last[1]:
            last[1] = max(last[1], end)
        else:
            merged.append([start, end])
    return merged
