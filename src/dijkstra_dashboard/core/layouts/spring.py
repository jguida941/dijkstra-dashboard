import random
from typing import Dict, Iterable, Tuple


def spring_layout(node_ids: Iterable[str],
                  edges: Iterable[Tuple[str, str]],
                  iterations: int = 50,
                  seed: int = 0,
                  width: float = 800.0,
                  height: float = 600.0) -> Dict[str, Tuple[float, float]]:
    ids = list(node_ids)
    if not ids:
        return {}

    rng = random.Random(seed)
    positions = {
        node_id: (rng.uniform(0, width), rng.uniform(0, height))
        for node_id in ids
    }
    disp = {node_id: [0.0, 0.0] for node_id in ids}

    area = width * height
    k = (area / len(ids)) ** 0.5

    def _cool(t: int) -> float:
        return max(0.1, (iterations - t) / iterations)

    edge_list = [(u, v) for u, v in edges if u in positions and v in positions]

    for t in range(iterations):
        for node_id in ids:
            disp[node_id][0] = 0.0
            disp[node_id][1] = 0.0

        for i, v in enumerate(ids):
            x_v, y_v = positions[v]
            for u in ids[i + 1:]:
                x_u, y_u = positions[u]
                dx = x_v - x_u
                dy = y_v - y_u
                dist = (dx * dx + dy * dy) ** 0.5 or 0.01
                force = k * k / dist
                disp[v][0] += dx / dist * force
                disp[v][1] += dy / dist * force
                disp[u][0] -= dx / dist * force
                disp[u][1] -= dy / dist * force

        for v, u in edge_list:
            x_v, y_v = positions[v]
            x_u, y_u = positions[u]
            dx = x_v - x_u
            dy = y_v - y_u
            dist = (dx * dx + dy * dy) ** 0.5 or 0.01
            force = dist * dist / k
            disp[v][0] -= dx / dist * force
            disp[v][1] -= dy / dist * force
            disp[u][0] += dx / dist * force
            disp[u][1] += dy / dist * force

        temp = _cool(t)
        for node_id in ids:
            dx, dy = disp[node_id]
            dist = (dx * dx + dy * dy) ** 0.5 or 0.01
            x, y = positions[node_id]
            x = min(width, max(0.0, x + (dx / dist) * min(dist, temp * k)))
            y = min(height, max(0.0, y + (dy / dist) * min(dist, temp * k)))
            positions[node_id] = (x, y)

    center_x = width / 2
    center_y = height / 2
    for node_id, (x, y) in positions.items():
        positions[node_id] = (x - center_x, y - center_y)

    return positions
