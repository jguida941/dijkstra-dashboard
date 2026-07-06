def shortest_path(graph, start, target=""):
    if hasattr(graph, "to_adjacency_dict"):
        graph = graph.to_adjacency_dict()

    unvisited = list(graph)
    distances = {node: 0 if node == start else float('inf') for node in graph}
    paths = {node: [] for node in graph}
    paths[start].append(start)

    while unvisited:
        current = min(unvisited, key=distances.get)
        
        for node, distance in graph[current]:
            if distance + distances[current] < distances[node]:
                distances[node] = distance + distances[current]
                paths[node] = paths[current] + [node]
                
        unvisited.remove(current)

    return distances, paths
