"""Shortest paths through a weighted directed graph."""

import heapq
import math


def shortest_path(graph, start, goal):
    """Return (total_cost, path) for a cheapest route from start to goal."""
    for node, edges in graph.items():
        for neighbour, cost in edges.items():
            if cost < 0:
                raise ValueError(
                    f"edge {node} -> {neighbour} has a negative cost {cost}"
                )

    if start == goal:
        return 0, [start]

    visited = set()
    queue = [(0, start, [start])]

    while queue:
        cost, node, path = heapq.heappop(queue)

        # A node is settled only when it comes *off* the queue, because that is
        # the moment we know no cheaper route to it is still waiting. Settling
        # it when it was pushed would lock in the first route found rather than
        # the cheapest one.
        if node in visited:
            continue
        visited.add(node)

        if node == goal:
            return cost, path

        for neighbour, edge_cost in graph.get(node, {}).items():
            if neighbour in visited:
                continue
            heapq.heappush(queue, (cost + edge_cost, neighbour, path + [neighbour]))

    return math.inf, []
