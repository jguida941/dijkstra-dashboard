import math
from typing import Dict, Iterable, Tuple


def circle_layout(node_ids: Iterable[str], radius: float = 200.0,
                  center: Tuple[float, float] = (0.0, 0.0)) -> Dict[str, Tuple[float, float]]:
    ids = list(node_ids)
    count = len(ids)
    if count == 0:
        return {}

    cx, cy = center
    angle_offset = -math.pi / 2
    positions: Dict[str, Tuple[float, float]] = {}

    for i, node_id in enumerate(ids):
        angle = angle_offset + 2 * math.pi * i / count
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        positions[node_id] = (x, y)

    return positions
