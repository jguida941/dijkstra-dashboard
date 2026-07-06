import math
from typing import Dict, Iterable, Tuple


def grid_layout(node_ids: Iterable[str], spacing: float = 100.0,
                columns: int | None = None,
                origin: Tuple[float, float] = (0.0, 0.0)) -> Dict[str, Tuple[float, float]]:
    ids = list(node_ids)
    count = len(ids)
    if count == 0:
        return {}

    if columns is None:
        columns = max(1, int(math.ceil(math.sqrt(count))))

    ox, oy = origin
    positions: Dict[str, Tuple[float, float]] = {}

    for idx, node_id in enumerate(ids):
        row = idx // columns
        col = idx % columns
        x = ox + col * spacing
        y = oy + row * spacing
        positions[node_id] = (x, y)

    return positions
