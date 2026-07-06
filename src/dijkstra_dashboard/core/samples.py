"""Built-in sample graphs (Qt-free).

Extracted from ``GraphView.setup_graph`` so the default demo graph is available
to core code and tests without touching the UI layer.
"""

from __future__ import annotations

from .graph import Graph
from .layouts.circle import circle_layout

#: Radius used by the boot demo layout: 35% of the nominal 600px minimum view
#: dimension (``min(800, 600) * 0.35``), matching GraphView.setup_graph at the
#: default window size.
DEMO_RADIUS = 210.0

_DEMO_NODES = ('A', 'B', 'C', 'D', 'E', 'F')
_DEMO_EDGES = (
    ('A', 'B', 5), ('A', 'C', 3), ('A', 'E', 11),
    ('B', 'C', 1), ('B', 'F', 2),
    ('C', 'D', 1), ('C', 'E', 5),
    ('D', 'E', 9), ('D', 'F', 3),
)


def default_demo_graph() -> Graph:
    """Return the classic A-F demo graph shown on application boot.

    Undirected, six nodes labelled A..F, nine weighted edges. Node positions
    come from :func:`dijkstra_dashboard.core.layouts.circle.circle_layout`,
    which reproduces GraphView.setup_graph's placement exactly (start angle
    -pi/2 at top center, origin-centered) with radius ``DEMO_RADIUS`` — so no
    trig is replicated here. Fully deterministic: repeated calls produce
    identical ``to_dict()`` output.
    """
    positions = circle_layout(_DEMO_NODES, radius=DEMO_RADIUS)

    graph = Graph(directed=False)
    for name in _DEMO_NODES:
        x, y = positions[name]
        graph.add_node(node_id=name, label=name, x=x, y=y)
    for start, end, weight in _DEMO_EDGES:
        graph.add_edge(start, end, weight)
    return graph
