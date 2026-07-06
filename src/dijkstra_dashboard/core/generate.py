"""Seeded random graph generation (Qt-free, deterministic per seed)."""

from __future__ import annotations

import random
from typing import List, Tuple

from .graph import Graph
from .layouts.circle import circle_layout
from .samples import DEMO_RADIUS


def _node_labels(count: int) -> List[str]:
    """Deterministic label scheme: ``A..Z`` for the first 26 nodes, then a
    numeric suffix that increments each time the alphabet wraps — ``A1, B1,
    ... Z1, A2, ...``. Index ``i`` maps to ``chr(ord('A') + i % 26)`` plus the
    suffix ``i // 26`` (omitted when zero)."""
    labels = []
    for i in range(count):
        letter = chr(ord('A') + i % 26)
        cycle = i // 26
        labels.append(letter if cycle == 0 else f"{letter}{cycle}")
    return labels


def random_graph(node_count: int, edge_density: float,
                 weight_range: Tuple[int, int] = (1, 9), seed=None,
                 directed: bool = False, connected: bool = True) -> Graph:
    """Generate a random graph, deterministic for a given ``seed``.

    All randomness flows through one ``random.Random(seed)`` instance, so the
    same arguments plus the same seed always yield an identical graph
    (identical ``to_dict()``).

    - ``node_count`` must be in [2, 50]; labels follow the A..Z / A1, B1, ...
      scheme of :func:`_node_labels` and double as node ids.
    - ``edge_density`` must be in [0.0, 1.0].
    - ``weight_range`` is an inclusive integer range; min must be >= 1 and
      <= max. Weights are drawn with ``rng.randint``.
    - ``connected=True`` first builds a random spanning tree: the node order
      is shuffled, then each node i (i >= 1) attaches to an rng-chosen earlier
      node in that order. For ``directed=True`` tree edges are oriented
      earlier -> later, so every node is reachable from the tree root. Extra
      edges are then sampled from the pool of remaining pairs:
      ``round(edge_density * len(pool))`` of them via ``rng.sample``.
    - ``connected=False`` skips the tree; the density applies to the whole
      pool of candidate pairs.
    - The candidate pool is every unordered node pair for undirected graphs
      and every ordered pair for directed graphs, excluding self-loops and
      already-existing edges.
    - Positions use the same circle layout as the demo sample graph.

    Raises ``ValueError`` for out-of-range arguments.
    """
    if not (2 <= node_count <= 50):
        raise ValueError("node_count must be between 2 and 50.")
    if not (0.0 <= edge_density <= 1.0):
        raise ValueError("edge_density must be between 0.0 and 1.0.")
    min_weight, max_weight = weight_range
    if min_weight > max_weight or min_weight < 1:
        raise ValueError("weight_range must satisfy 1 <= min <= max.")

    rng = random.Random(seed)
    labels = _node_labels(node_count)
    positions = circle_layout(labels, radius=DEMO_RADIUS)

    graph = Graph(directed=directed)
    for label in labels:
        x, y = positions[label]
        graph.add_node(node_id=label, label=label, x=x, y=y)

    existing = set()

    def _key(u: str, v: str):
        return (u, v) if directed else frozenset((u, v))

    if connected:
        order = list(labels)
        rng.shuffle(order)
        for i in range(1, node_count):
            parent = order[rng.randrange(i)]
            child = order[i]
            graph.add_edge(parent, child, rng.randint(min_weight, max_weight))
            existing.add(_key(parent, child))

    if directed:
        pool = [(u, v) for u in labels for v in labels
                if u != v and (u, v) not in existing]
    else:
        pool = [(labels[i], labels[j])
                for i in range(node_count) for j in range(i + 1, node_count)
                if _key(labels[i], labels[j]) not in existing]

    extra_count = round(edge_density * len(pool))
    for start, end in rng.sample(pool, extra_count):
        graph.add_edge(start, end, rng.randint(min_weight, max_weight))

    return graph
