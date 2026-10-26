"""
A* search on the city grid.

f(n) = g(n) + h(n)
  g(n) : travel cost from the start to n (road tile = 1, traffic tile = 3)
  h(n) : Manhattan distance |dr| + |dc| to the goal

The cheapest possible tile costs 1 and the ambulance can only move up, down,
left or right, so Manhattan distance never overestimates the real cost.
That makes the heuristic ADMISSIBLE, so A* always returns the cheapest route.

Dijkstra is the same algorithm with h(n) = 0. We run it too, only to show
how many extra tiles it has to check.
"""
import heapq


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def zero(a, b):
    return 0


def astar(city, start, goal, heuristic=manhattan):
    """Returns (path, cost, explored).
    path     : list of (row, col) tiles from start to goal, or None
    cost     : total travel cost of the path
    explored : tiles A* expanded, in order (used to draw the search)"""
    open_heap = [(heuristic(start, goal), 0, start)]
    g = {start: 0}
    parent = {start: None}
    closed = set()
    explored = []
    while open_heap:
        _, cost, node = heapq.heappop(open_heap)
        if node in closed:
            continue
        closed.add(node)
        explored.append(node)
        if node == goal:
            break
        for nxt in city.neighbors(node):
            new_cost = cost + city.cost(nxt)
            if new_cost < g.get(nxt, float("inf")):
                g[nxt] = new_cost
                parent[nxt] = node
                heapq.heappush(open_heap, (new_cost + heuristic(nxt, goal), new_cost, nxt))
    if goal not in closed:
        return None, float("inf"), explored
    path, node = [], goal
    while node is not None:
        path.append(node)
        node = parent[node]
    return path[::-1], g[goal], explored


def dijkstra(city, start, goal):
    return astar(city, start, goal, heuristic=zero)
