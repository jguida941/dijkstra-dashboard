from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from .schema import edge_id
from .types import Edge, GraphStats, Node


class Graph:
    def __init__(self, directed: bool = False, metadata: dict | None = None):
        self._directed = bool(directed)
        self._nodes: Dict[str, Node] = {}
        self._edges: Dict[str, Edge] = {}
        self._metadata = dict(metadata or {})
        self._next_id = 1

    @property
    def directed(self) -> bool:
        return self._directed

    @property
    def metadata(self) -> dict:
        return dict(self._metadata)

    def set_metadata(self, metadata: dict) -> None:
        self._metadata = dict(metadata)

    def _generate_node_id(self) -> str:
        while True:
            node_id = f"n{self._next_id}"
            self._next_id += 1
            if node_id not in self._nodes:
                return node_id

    def add_node(self, node_id: str | None = None, label: str | None = None,
                 x: float = 0, y: float = 0) -> str:
        if node_id is None:
            node_id = self._generate_node_id()
        if not isinstance(node_id, str) or not node_id:
            raise ValueError("Node id must be a non-empty string.")
        if node_id in self._nodes:
            raise ValueError(f"Node '{node_id}' already exists.")
        if label is None:
            label = node_id
        if not isinstance(label, str):
            raise ValueError("Node label must be a string.")
        self._nodes[node_id] = Node(id=node_id, label=label, x=float(x), y=float(y))
        if node_id.startswith("n") and node_id[1:].isdigit():
            self._next_id = max(self._next_id, int(node_id[1:]) + 1)
        return node_id

    def remove_node(self, node_id: str) -> None:
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        del self._nodes[node_id]
        to_remove = [edge_id for edge_id, edge in self._edges.items()
                     if edge.start == node_id or edge.end == node_id]
        for edge_id_key in to_remove:
            del self._edges[edge_id_key]

    def rename_node(self, node_id: str, label: str) -> None:
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        if not isinstance(label, str):
            raise ValueError("Node label must be a string.")
        node = self._nodes[node_id]
        self._nodes[node_id] = Node(id=node.id, label=label, x=node.x, y=node.y)

    def _normalize_edge(self, start: str, end: str) -> tuple[str, str]:
        if self._directed:
            return start, end
        if start <= end:
            return start, end
        return end, start

    def add_edge(self, start: str, end: str, weight: float) -> None:
        if start not in self._nodes or end not in self._nodes:
            raise ValueError("Both nodes must exist to add an edge.")
        if start == end:
            raise ValueError("Edge start and end cannot be the same.")
        if not isinstance(weight, (int, float)):
            raise ValueError("Edge weight must be numeric.")

        norm_start, norm_end = self._normalize_edge(start, end)
        edge_key = edge_id(norm_start, norm_end, self._directed)
        if edge_key in self._edges:
            raise ValueError("Edge already exists.")

        self._edges[edge_key] = Edge(id=edge_key, start=norm_start,
                                     end=norm_end, weight=float(weight))

    def remove_edge(self, start: str, end: str) -> None:
        norm_start, norm_end = self._normalize_edge(start, end)
        edge_key = edge_id(norm_start, norm_end, self._directed)
        if edge_key not in self._edges:
            raise ValueError("Edge not found.")
        del self._edges[edge_key]

    def update_edge(self, start: str, end: str, weight: float) -> None:
        if not isinstance(weight, (int, float)):
            raise ValueError("Edge weight must be numeric.")
        norm_start, norm_end = self._normalize_edge(start, end)
        edge_key = edge_id(norm_start, norm_end, self._directed)
        if edge_key not in self._edges:
            raise ValueError("Edge not found.")
        edge = self._edges[edge_key]
        self._edges[edge_key] = Edge(id=edge.id, start=edge.start, end=edge.end,
                                     weight=float(weight))

    def get_neighbors(self, node_id: str) -> List[Tuple[str, float]]:
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        neighbors: List[Tuple[str, float]] = []
        for edge in self._edges.values():
            if self._directed:
                if edge.start == node_id:
                    neighbors.append((edge.end, edge.weight))
            else:
                if edge.start == node_id:
                    neighbors.append((edge.end, edge.weight))
                elif edge.end == node_id:
                    neighbors.append((edge.start, edge.weight))
        return neighbors

    def get_nodes(self) -> List[str]:
        return list(self._nodes.keys())

    def get_node_label(self, node_id: str) -> str:
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        return self._nodes[node_id].label

    def get_edges(self) -> List[Tuple[str, str, float]]:
        return [(edge.start, edge.end, edge.weight) for edge in self._edges.values()]

    def get_node_position(self, node_id: str) -> tuple[float, float]:
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        node = self._nodes[node_id]
        return (node.x, node.y)

    def set_node_position(self, node_id: str, x: float, y: float) -> None:
        if node_id not in self._nodes:
            raise ValueError(f"Node '{node_id}' not found.")
        node = self._nodes[node_id]
        self._nodes[node_id] = Node(id=node.id, label=node.label, x=float(x), y=float(y))

    def to_dict(self) -> dict:
        from .serialization import graph_to_dict

        return graph_to_dict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Graph":
        from .serialization import dict_to_graph

        return dict_to_graph(data)

    def to_adjacency_dict(self) -> dict:
        adjacency = {node_id: [] for node_id in self._nodes.keys()}
        for edge in self._edges.values():
            adjacency[edge.start].append((edge.end, edge.weight))
            if not self._directed:
                adjacency[edge.end].append((edge.start, edge.weight))
        return adjacency

    def set_directed(self, directed: bool) -> None:
        directed = bool(directed)
        if directed == self._directed:
            return

        if directed:
            new_edges: Dict[str, Edge] = {}
            for edge in self._edges.values():
                forward_id = edge_id(edge.start, edge.end, True)
                new_edges[forward_id] = Edge(id=forward_id, start=edge.start,
                                             end=edge.end, weight=edge.weight)
            self._edges = new_edges
        else:
            new_edges = {}
            for edge in self._edges.values():
                norm_start, norm_end = sorted([edge.start, edge.end])
                edge_key = edge_id(norm_start, norm_end, False)
                if edge_key in new_edges:
                    existing = new_edges[edge_key]
                    if edge.weight < existing.weight:
                        new_edges[edge_key] = Edge(id=edge_key, start=norm_start,
                                                   end=norm_end, weight=edge.weight)
                else:
                    new_edges[edge_key] = Edge(id=edge_key, start=norm_start,
                                               end=norm_end, weight=edge.weight)
            self._edges = new_edges

        self._directed = directed

    def get_stats(self) -> GraphStats:
        return GraphStats(node_count=len(self._nodes), edge_count=len(self._edges),
                          directed=self._directed)

    def nodes(self) -> Iterable[Node]:
        return list(self._nodes.values())

    def edges(self) -> Iterable[Edge]:
        return list(self._edges.values())
