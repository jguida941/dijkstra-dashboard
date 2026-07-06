from __future__ import annotations

from typing import Iterable

from .base import AlgorithmParam, AlgorithmResult, AlgorithmSpec, AlgorithmStep, PathfindingAlgorithm
from .registry import register_algorithm
from .runner import result_from_steps
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
    pseudocode = [
        "function dijkstra(graph, start, target):",
        "  for each node v: dist[v] = \u221e",
        "  dist[start] = 0",
        "  unvisited = all nodes",
        "  while unvisited is not empty:",
        "    u = unvisited node with smallest dist",
        "    if dist[u] = \u221e: break",
        "    settle u  (remove from unvisited)",
        "    if u = target: break",
        "    for each edge (u, v, weight):",
        "      if v is settled: skip edge",
        "      if dist[u] + weight < dist[v]:",
        "        dist[v] = dist[u] + weight; prev[v] = u",
        "      else: keep dist[v]  (no improvement)",
        "  return dist, prev",
    ]
    step_line_map = {
        ("visit", None): [5, 7],
        ("relax", None): [11, 12],
        ("skip", "visited"): [10],
        ("skip", "worse"): [11, 13],
        ("final", "target_found"): [8, 14],
        ("final", "unreachable"): [6, 14],
        ("final", None): [14],
    }

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

        steps = list(self.iter_steps(graph, params))
        return result_from_steps(steps, graph.get_nodes(), start, target, "single_path")

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
                new_dist = distances[current] + weight
                if neighbor not in unvisited:
                    yield {
                        "kind": "skip",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": distances[neighbor],
                        "new_distance": new_dist,
                        "payload": {"reason": "visited"},
                    }
                    continue
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
                else:
                    yield {
                        "kind": "skip",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": distances[neighbor],
                        "new_distance": new_dist,
                        "payload": {"reason": "worse"},
                    }

        if target is not None:
            final_distance = distances.get(target, float("inf"))
            reason = "target_found" if final_distance < float("inf") else "unreachable"
            yield {
                "kind": "final",
                "node": target,
                "edge": None,
                "old_distance": None,
                "new_distance": final_distance,
                "payload": {"reason": reason},
            }

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

try:
    register_algorithm(DijkstraAlgorithm.spec, DijkstraAlgorithm)
except ValueError:
    pass
