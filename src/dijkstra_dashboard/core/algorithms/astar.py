from __future__ import annotations

import math
from typing import Iterable

from .base import AlgorithmParam, AlgorithmResult, AlgorithmSpec, AlgorithmStep, PathfindingAlgorithm
from .registry import register_algorithm
from .runner import result_from_steps
from ..errors import AlgorithmError
from ..graph import Graph


class AStarAlgorithm(PathfindingAlgorithm):
    spec = AlgorithmSpec(
        name="astar",
        description="A* with spatial heuristic (needs target)",
        inputs=[
            AlgorithmParam(name="start", type="node_id", required=True),
            AlgorithmParam(name="target", type="node_id", required=True),
        ],
        output_kind="single_path",
        constraints={"non_negative": True, "requires_target": True},
    )
    pseudocode = [
        "function a_star(graph, start, target):",
        "  for each node v: g[v] = ∞",
        "  g[start] = 0",
        "  open = all nodes  (keyed by f = g + h)",
        "  while open is not empty:",
        "    u = open node with smallest f = g + h",
        "    if g[u] = ∞: break",
        "    settle u  (remove from open)",
        "    if u = target: break",
        "    for each edge (u, v, weight):",
        "      if v is settled: skip edge",
        "      if g[u] + weight < g[v]:",
        "        g[v] = g[u] + weight; prev[v] = u",
        "      else: keep g[v]  (no improvement)",
        "  return g, prev",
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
                raise AlgorithmError("A* does not support negative weights.")

    def _euclid(self, graph: Graph, a: str, b: str) -> float:
        ax, ay = graph.get_node_position(a)
        bx, by = graph.get_node_position(b)
        return math.hypot(ax - bx, ay - by)

    def _heuristic_scale(self, graph: Graph) -> float:
        """Largest c keeping h admissible+consistent: min weight/euclidean over edges."""
        ratios: list[float] = []
        for start, end, weight in graph.get_edges():
            length = self._euclid(graph, start, end)
            if length > 1e-9:
                ratios.append(weight / length)
        if not ratios:
            return 0.0
        scale = min(ratios)
        if scale < 0:
            return 0.0
        return scale

    def solve(self, graph: Graph, params: dict) -> AlgorithmResult:
        start = params.get("start")
        if start is None:
            raise AlgorithmError("Missing required parameter: start")
        if params.get("target") is None:
            raise AlgorithmError("A* requires a target.")

        self._validate_graph(graph)

        steps = list(self.iter_steps(graph, params))
        return result_from_steps(steps, graph.get_nodes(), start, params["target"], "single_path")

    def iter_steps(self, graph: Graph, params: dict,
                   mode: str = "delta") -> Iterable[AlgorithmStep]:
        start = params.get("start")
        if start is None:
            raise AlgorithmError("Missing required parameter: start")
        target = params.get("target")
        if target is None:
            raise AlgorithmError("A* requires a target.")

        self._validate_graph(graph)

        adjacency = graph.to_adjacency_dict()
        if start not in adjacency:
            raise AlgorithmError(f"Start node '{start}' not found.")

        scale = self._heuristic_scale(graph)

        def h(node: str) -> float:
            return scale * self._euclid(graph, node, target)

        unvisited = set(adjacency.keys())
        g = {node: float("inf") for node in adjacency}
        prev: dict[str, str] = {}
        g[start] = 0.0

        while unvisited:
            current, current_g = self._select_current(unvisited, g, h, target)
            if current is None or current_g == float("inf"):
                break
            unvisited.remove(current)

            h_value = h(current)
            payload = {"h": h_value, "f": current_g + h_value}
            if mode == "snapshot":
                payload["distances"] = dict(g)
                payload["frontier"] = list(unvisited)

            yield {
                "kind": "visit",
                "node": current,
                "edge": None,
                "old_distance": None,
                "new_distance": current_g,
                "payload": payload,
            }

            if current == target:
                break

            for neighbor, weight in adjacency[current]:
                new_g = g[current] + weight
                if neighbor not in unvisited:
                    yield {
                        "kind": "skip",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": g[neighbor],
                        "new_distance": new_g,
                        "payload": {"reason": "visited"},
                    }
                    continue
                if new_g < g[neighbor]:
                    old_g = g[neighbor]
                    g[neighbor] = new_g
                    prev[neighbor] = current
                    relax_payload = None
                    if mode == "snapshot":
                        relax_payload = {"distances": dict(g)}
                    yield {
                        "kind": "relax",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": old_g,
                        "new_distance": new_g,
                        "payload": relax_payload,
                    }
                else:
                    yield {
                        "kind": "skip",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": g[neighbor],
                        "new_distance": new_g,
                        "payload": {"reason": "worse"},
                    }

        final_distance = g.get(target, float("inf"))
        reason = "target_found" if final_distance < float("inf") else "unreachable"
        yield {
            "kind": "final",
            "node": target,
            "edge": None,
            "old_distance": None,
            "new_distance": final_distance,
            "payload": {"reason": reason, "heuristic_scale": scale},
        }

    def _select_current(self, unvisited: set[str], g: dict[str, float],
                        h, target: str | None) -> tuple[str | None, float]:
        min_node = None
        min_key = None  # (f = g + h, h, node_id)
        for node in unvisited:
            h_value = h(node)
            key = (g[node] + h_value, h_value, node)
            if min_key is None or key < min_key:
                min_key = key
                min_node = node

        if min_node is None:
            return None, float("inf")

        # Target-preferred tie-break: prefer the target when its f ties the minimum.
        if target is not None and target in unvisited:
            target_f = g[target] + h(target)
            if target_f == min_key[0]:
                return target, g[target]

        return min_node, g[min_node]


try:
    register_algorithm(AStarAlgorithm.spec, AStarAlgorithm)
except ValueError:
    pass
