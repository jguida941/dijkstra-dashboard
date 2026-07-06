"""
Dijkstra's Shortest Path Algorithm
==================================

A simple implementation of Dijkstra's algorithm to find the shortest path
between nodes in a weighted graph.

Graph Format:
    Dictionary where keys are node names and values are lists of
    (neighbor, weight) tuples representing edges.
"""

# Example graph matching the visualizer's default layout
my_graph = {
    'A': [('B', 5), ('C', 3), ('E', 11)],
    'B': [('A', 5), ('C', 1), ('F', 2)],
    'C': [('A', 3), ('B', 1), ('D', 1), ('E', 5)],
    'D': [('C', 1), ('E', 9), ('F', 3)],
    'E': [('A', 11), ('C', 5), ('D', 9)],
    'F': [('B', 2), ('D', 3)]
}


def shortest_path(graph, start, target=""):
    """
    Find the shortest path from start node to target (or all nodes).

    Args:
        graph: Dictionary of {node: [(neighbor, weight), ...]}
        start: Starting node name
        target: Optional target node (if empty, finds paths to all nodes)

    Returns:
        distances: Dict of shortest distance from start to each node
        paths: Dict of shortest path (as list) from start to each node

    Example:
        >>> distances, paths = shortest_path(my_graph, 'A', 'F')
        >>> print(paths['F'])  # ['A', 'C', 'D', 'F']
    """
    # Track which nodes we haven't processed yet
    unvisited = list(graph)

    # Initialize all distances to infinity, except start which is 0
    distances = {node: 0 if node == start else float('inf') for node in graph}

    # Track the actual path to each node
    paths = {node: [] for node in graph}
    paths[start].append(start)

    # Main algorithm loop - process nodes until all are visited
    while unvisited:
        # Greedy step: pick the unvisited node with smallest distance
        current = min(unvisited, key=distances.get)

        # Check all neighbors of current node
        for neighbor, weight in graph[current]:
            new_distance = distances[current] + weight

            # Relaxation: if we found a shorter path, update it
            if new_distance < distances[neighbor]:
                distances[neighbor] = new_distance
                paths[neighbor] = paths[current] + [neighbor]

        # Mark current node as visited
        unvisited.remove(current)

    # Print results
    targets_to_print = [target] if target else graph
    for node in targets_to_print:
        if node == start:
            continue
        print(f'\n{start}-{node} distance: {distances[node]}\nPath: {" -> ".join(paths[node])}')

    return distances, paths


if __name__ == "__main__":
    # Run example: find shortest path from A to F
    shortest_path(my_graph, 'A', 'F')
