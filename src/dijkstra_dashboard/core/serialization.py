from __future__ import annotations

from typing import Any, Dict

from .errors import ValidationError
from .schema import GRAPH_SCHEMA_VERSION, new_graph_dict
from .validation import validate_graph_data
from .graph import Graph


def graph_to_dict(graph: Graph) -> Dict[str, Any]:
    data = new_graph_dict(directed=graph.directed, metadata=graph.metadata)

    nodes = {}
    for node in graph.nodes():
        nodes[node.id] = {
            "label": node.label,
            "x": node.x,
            "y": node.y,
        }

    edges = []
    for edge in graph.edges():
        edges.append({
            "id": edge.id,
            "start": edge.start,
            "end": edge.end,
            "weight": edge.weight,
        })

    data["nodes"] = nodes
    data["edges"] = edges
    data["version"] = GRAPH_SCHEMA_VERSION

    return data


def dict_to_graph(data: Dict[str, Any]) -> Graph:
    issues = validate_graph_data(data)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise ValidationError(errors)

    directed = bool(data.get("directed", False))
    metadata = data.get("metadata") or {}
    graph = Graph(directed=directed, metadata=metadata)

    nodes = data.get("nodes", {})
    for node_id, node_data in nodes.items():
        label = node_data.get("label") if isinstance(node_data, dict) else None
        x_val = node_data.get("x", 0) if isinstance(node_data, dict) else 0
        y_val = node_data.get("y", 0) if isinstance(node_data, dict) else 0
        graph.add_node(node_id=node_id, label=label, x=x_val, y=y_val)

    edges = data.get("edges", [])
    for edge_data in edges:
        if not isinstance(edge_data, dict):
            continue
        start = edge_data.get("start")
        end = edge_data.get("end")
        weight = edge_data.get("weight")
        if start in graph.get_nodes() and end in graph.get_nodes():
            graph.add_edge(start, end, weight)

    return graph
