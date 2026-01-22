from typing import Any, Dict

GRAPH_SCHEMA_VERSION = 1


def edge_id(start: str, end: str, directed: bool) -> str:
    if directed:
        return f"{start}->{end}"
    ordered = sorted([start, end])
    return f"{ordered[0]}--{ordered[1]}"


def new_graph_dict(directed: bool = False,
                   metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
    return {
        "version": GRAPH_SCHEMA_VERSION,
        "directed": directed,
        "metadata": metadata or {},
        "nodes": {},
        "edges": [],
    }
