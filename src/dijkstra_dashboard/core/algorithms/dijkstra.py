from __future__ import annotations

from typing import Iterable

from .base import AlgorithmParam, AlgorithmResult, AlgorithmSpec, AlgorithmStep, PathfindingAlgorithm
from .registry import register_algorithm
from ..errors import AlgorithmError
from ..graph import Graph


class DijkstraAlgorithm(PathfindingAlgorithm):
    spec = AlgorithmSpec(
        name="dijkstra",
        description="Shortest path for non-negative weights",
        inputs=[
            AlgorithmParam(name="start", type="node_id", required=True),
            AlgorithmParam(name="target", type="node_id", required=False),
        ],
        output_kind="single_path",
        constraints={"non_negative": True},
    )

    def _validate_graph(self, graph: Graph) -> None:
        for edge in graph.edges():
            if edge.weight < 0:
                raise AlgorithmError("Dijkstra does not support negative weights.")

    def solve(self, graph: Graph, params: dict) -> AlgorithmResult:
        start = params.get("start")
        if start is None:
            raise AlgorithmError("Missing required parameter: start")
        target = params.get("target")

        self._validate_graph(graph)

        distances, prev, visited_order = self._run(graph, start, target)
        paths = self._build_paths(prev, start, distances)

        if target is None:
            path = []
            distance = None
        else:
            path = paths.get(target, [])
            distance = distances.get(target, float("inf"))

        return AlgorithmResult(
            kind="single_path",
            path=path,
            distance=distance,
            distances=distances,
            paths=paths,
            visited_order=visited_order,
            steps=None,
        )

    def iter_steps(self, graph: Graph, params: dict,
                   mode: str = "delta") -> Iterable[AlgorithmStep]:
        start = params.get("start")
        if start is None:
            raise AlgorithmError("Missing required parameter: start")
        target = params.get("target")

        self._validate_graph(graph)

        adjacency = graph.to_adjacency_dict()
        if start not in adjacency:
            raise AlgorithmError(f"Start node '{start}' not found.")
        unvisited = set(adjacency.keys())
        distances = {node: float("inf") for node in adjacency}
        prev: dict[str, str] = {}
        distances[start] = 0.0

        while unvisited:
            current, current_dist = self._select_current(unvisited, distances, target)
            if current is None or current_dist == float("inf"):
                break
            unvisited.remove(current)

            payload = None
            if mode == "snapshot":
                payload = {"distances": dict(distances), "frontier": list(unvisited)}

            yield {
                "kind": "visit",
                "node": current,
                "edge": None,
                "old_distance": None,
                "new_distance": distances[current],
                "payload": payload,
            }

            if target is not None and current == target:
                break

            for neighbor, weight in adjacency[current]:
                if neighbor not in unvisited:
                    continue
                new_dist = distances[current] + weight
                if new_dist < distances[neighbor]:
                    old_dist = distances[neighbor]
                    distances[neighbor] = new_dist
                    prev[neighbor] = current
                    payload = None
                    if mode == "snapshot":
                        payload = {"distances": dict(distances)}
                    yield {
                        "kind": "relax",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": old_dist,
                        "new_distance": new_dist,
                        "payload": payload,
                    }

        if target is not None:
            yield {
                "kind": "final",
                "node": target,
                "edge": None,
                "old_distance": None,
                "new_distance": distances.get(target, float("inf")),
                "payload": None,
            }

    def _run(self, graph: Graph, start: str, target: str | None):
        adjacency = graph.to_adjacency_dict()
        unvisited = set(adjacency.keys())
        distances = {node: float("inf") for node in adjacency}
        prev: dict[str, str] = {}
        visited_order: list[str] = []

        if start not in adjacency:
            raise AlgorithmError(f"Start node '{start}' not found.")

        distances[start] = 0.0

        while unvisited:
            current, current_dist = self._select_current(unvisited, distances, target)
            if current is None or current_dist == float("inf"):
                break
            unvisited.remove(current)
            visited_order.append(current)

            if target is not None and current == target:
                break

            for neighbor, weight in adjacency[current]:
                if neighbor not in unvisited:
                    continue
                new_dist = distances[current] + weight
                if new_dist < distances[neighbor]:
                    distances[neighbor] = new_dist
                    prev[neighbor] = current

        return distances, prev, visited_order

    def _select_current(self, unvisited: set[str],
                        distances: dict[str, float],
                        target: str | None) -> tuple[str | None, float]:
        min_node = None
        min_dist = float("inf")
        for node in unvisited:
            dist = distances[node]
            if dist < min_dist:
                min_node = node
                min_dist = dist
            elif dist == min_dist and min_node is not None and node < min_node:
                min_node = node

        if min_node is None:
            return None, float("inf")

        if target is not None and target in unvisited and distances[target] == min_dist:
            return target, min_dist

        return min_node, min_dist

    def _build_paths(self, prev: dict[str, str], start: str,
                     distances: dict[str, float]) -> dict[str, list[str]]:
        paths: dict[str, list[str]] = {}
        for node, dist in distances.items():
            if dist == float("inf"):
                paths[node] = []
                continue
            path = [node]
            while path[-1] != start:
                parent = prev.get(path[-1])
                if parent is None:
                    path = []
                    break
                path.append(parent)
            paths[node] = list(reversed(path))
        return paths


try:
    register_algorithm(DijkstraAlgorithm.spec)
except ValueError:
    pass
