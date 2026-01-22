from __future__ import annotations

from collections import deque
from typing import Any, Dict, Iterable

from .errors import ValidationError
from .schema import GRAPH_SCHEMA_VERSION, edge_id
from .types import GraphIssue


def _issue(code: str, message: str, severity: str, path: str | None = None) -> GraphIssue:
    return GraphIssue(code=code, message=message, severity=severity, path=path)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float))


def _build_undirected_adjacency(nodes: Iterable[str], edges: list[dict]) -> Dict[str, set[str]]:
    adjacency: Dict[str, set[str]] = {node_id: set() for node_id in nodes}
    for edge in edges:
        start = edge.get("start")
        end = edge.get("end")
        if start in adjacency and end in adjacency:
            adjacency[start].add(end)
            adjacency[end].add(start)
    return adjacency


def _is_connected(nodes: list[str], edges: list[dict]) -> bool:
    if not nodes:
        return True

    adjacency = _build_undirected_adjacency(nodes, edges)
    visited = set()
    queue: deque[str] = deque([nodes[0]])

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        for neighbor in adjacency[current]:
            if neighbor not in visited:
                queue.append(neighbor)

    return len(visited) == len(nodes)


def validate_graph_data(data: Dict[str, Any]) -> list[GraphIssue]:
    issues: list[GraphIssue] = []

    if not isinstance(data, dict):
        return [_issue("invalid_type", "Graph data must be a dictionary.", "error")]

    version = data.get("version")
    if version != GRAPH_SCHEMA_VERSION:
        issues.append(_issue(
            "invalid_version",
            f"Unsupported graph version: {version}",
            "error",
            path="version",
        ))

    directed = data.get("directed")
    if not isinstance(directed, bool):
        issues.append(_issue(
            "invalid_directed",
            "Graph 'directed' must be a boolean.",
            "error",
            path="directed",
        ))
        directed = False

    nodes = data.get("nodes")
    if not isinstance(nodes, dict):
        issues.append(_issue(
            "invalid_nodes",
            "Graph 'nodes' must be a dictionary.",
            "error",
            path="nodes",
        ))
        nodes = {}

    edges = data.get("edges")
    if not isinstance(edges, list):
        issues.append(_issue(
            "invalid_edges",
            "Graph 'edges' must be a list.",
            "error",
            path="edges",
        ))
        edges = []

    for node_id, node_data in nodes.items():
        if not isinstance(node_id, str) or not node_id:
            issues.append(_issue(
                "invalid_node_id",
                "Node IDs must be non-empty strings.",
                "error",
                path=f"nodes.{node_id}",
            ))
            continue

        if not isinstance(node_data, dict):
            issues.append(_issue(
                "invalid_node",
                "Node data must be a dictionary.",
                "error",
                path=f"nodes.{node_id}",
            ))
            continue

        label = node_data.get("label")
        if label is None:
            issues.append(_issue(
                "missing_label",
                f"Node '{node_id}' is missing a label.",
                "warning",
                path=f"nodes.{node_id}.label",
            ))
        elif not isinstance(label, str):
            issues.append(_issue(
                "invalid_label",
                f"Node '{node_id}' label must be a string.",
                "error",
                path=f"nodes.{node_id}.label",
            ))

        x_val = node_data.get("x", 0)
        y_val = node_data.get("y", 0)
        if not _is_number(x_val):
            issues.append(_issue(
                "invalid_x",
                f"Node '{node_id}' x must be numeric.",
                "error",
                path=f"nodes.{node_id}.x",
            ))
        if not _is_number(y_val):
            issues.append(_issue(
                "invalid_y",
                f"Node '{node_id}' y must be numeric.",
                "error",
                path=f"nodes.{node_id}.y",
            ))

    edge_keys: set[tuple[str, str]] = set()
    for idx, edge in enumerate(edges):
        path = f"edges[{idx}]"
        if not isinstance(edge, dict):
            issues.append(_issue(
                "invalid_edge",
                "Edge must be a dictionary.",
                "error",
                path=path,
            ))
            continue

        start = edge.get("start")
        end = edge.get("end")
        weight = edge.get("weight")

        if not isinstance(start, str) or not isinstance(end, str):
            issues.append(_issue(
                "invalid_edge_nodes",
                "Edge 'start' and 'end' must be strings.",
                "error",
                path=path,
            ))
            continue

        if start not in nodes or end not in nodes:
            issues.append(_issue(
                "edge_missing_node",
                "Edge references missing node IDs.",
                "error",
                path=path,
            ))

        if start == end:
            issues.append(_issue(
                "self_loop",
                "Edge start and end cannot be the same.",
                "error",
                path=path,
            ))

        if not _is_number(weight):
            issues.append(_issue(
                "invalid_weight",
                "Edge weight must be numeric.",
                "error",
                path=f"{path}.weight",
            ))
        elif weight < 0:
            issues.append(_issue(
                "negative_weight",
                "Edge has negative weight; only some algorithms support this.",
                "warning",
                path=f"{path}.weight",
            ))

        edge_key = (start, end) if directed else tuple(sorted([start, end]))
        if edge_key in edge_keys:
            issues.append(_issue(
                "duplicate_edge",
                "Duplicate edge detected.",
                "error",
                path=path,
            ))
        else:
            edge_keys.add(edge_key)

        expected_id = edge_id(start, end, directed)
        provided_id = edge.get("id")
        if provided_id is None:
            issues.append(_issue(
                "missing_edge_id",
                "Edge id is missing; expected deterministic id.",
                "warning",
                path=f"{path}.id",
            ))
        elif not isinstance(provided_id, str):
            issues.append(_issue(
                "invalid_edge_id",
                "Edge id must be a string.",
                "error",
                path=f"{path}.id",
            ))
        elif provided_id != expected_id:
            issues.append(_issue(
                "edge_id_mismatch",
                f"Edge id '{provided_id}' does not match expected '{expected_id}'.",
                "warning",
                path=f"{path}.id",
            ))

    node_ids = [node_id for node_id in nodes.keys() if isinstance(node_id, str)]
    if node_ids and not _is_connected(node_ids, edges):
        issues.append(_issue(
            "graph_disconnected",
            "Graph is disconnected; some nodes may be unreachable.",
            "warning",
            path="edges",
        ))

    return issues


def validate_graph(graph: Any) -> list[GraphIssue]:
    if isinstance(graph, dict):
        return validate_graph_data(graph)

    if hasattr(graph, "to_dict"):
        return validate_graph_data(graph.to_dict())

    return [_issue("invalid_type", "Unsupported graph type for validation.", "error")]


def assert_valid(graph: Any) -> list[GraphIssue]:
    issues = validate_graph(graph)
    errors = [issue for issue in issues if issue.severity == "error"]
    if errors:
        raise ValidationError(errors)
    return issues
