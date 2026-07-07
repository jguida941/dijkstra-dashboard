from __future__ import annotations

from typing import Iterable

from .base import AlgorithmParam, AlgorithmResult, AlgorithmSpec, AlgorithmStep, PathfindingAlgorithm
from .registry import register_algorithm
from .runner import result_from_steps
from ..errors import AlgorithmError
from ..graph import Graph


class BellmanFordAlgorithm(PathfindingAlgorithm):
    spec = AlgorithmSpec(
        name="bellman-ford",
        description="Shortest path with negative weights + cycle detection",
        inputs=[
            AlgorithmParam(name="start", type="node_id", required=True),
            AlgorithmParam(name="target", type="node_id", required=False),
        ],
        output_kind="single_path",
        constraints={"allows_negative": True},
    )
    pseudocode = [
        "function bellman_ford(graph, start):",
        "  for each node v: dist[v] = ∞",
        "  dist[start] = 0",
        "  for pass = 1 to |V| - 1:",
        "    changed = false",
        "    for each edge (u, v, w):",
        "      if dist[u] + w < dist[v]:",
        "        dist[v] = dist[u] + w; prev[v] = u; changed = true",
        "      else: keep dist[v]  (no improvement)",
        "    if not changed: break  (converged)",
        "  detection pass: for each edge (u, v, w):",
        "    if dist[u] + w < dist[v]: report negative cycle",
        "  return dist, prev",
    ]
    step_line_map = {
        ("visit", None): [3, 4],
        ("relax", None): [6, 7],
        ("skip", "worse"): [6, 8],
        ("final", "target_found"): [9, 12],
        ("final", "unreachable"): [1, 12],
        ("final", None): [10, 11],
    }

    def _directed_edges(self, graph: Graph) -> list[tuple[str, str, float]]:
        if graph.directed:
            return list(graph.get_edges())
        directed: list[tuple[str, str, float]] = []
        for start, end, weight in graph.get_edges():
            directed.append((start, end, weight))
            directed.append((end, start, weight))
        return directed

    def solve(self, graph: Graph, params: dict) -> AlgorithmResult:
        start = params.get("start")
        if start is None:
            raise AlgorithmError("Missing required parameter: start")
        target = params.get("target")

        steps = list(self.iter_steps(graph, params))
        return result_from_steps(steps, graph.get_nodes(), start, target, "single_path")

    def iter_steps(self, graph: Graph, params: dict,
                   mode: str = "delta") -> Iterable[AlgorithmStep]:
        start = params.get("start")
        if start is None:
            raise AlgorithmError("Missing required parameter: start")
        target = params.get("target")

        nodes = graph.get_nodes()
        if start not in nodes:
            raise AlgorithmError(f"Start node '{start}' not found.")

        edges = self._directed_edges(graph)
        dist = {node: float("inf") for node in nodes}
        prev: dict[str, str] = {}
        dist[start] = 0.0

        # Seed the source (dist[start] = 0) into the fold. Pass markers carry node=None
        # so this edge-free relax is how the replayable distances learn the origin's 0,
        # while leaving visited_order and prev untouched (the source has no parent).
        yield {
            "kind": "relax",
            "node": start,
            "edge": None,
            "old_distance": float("inf"),
            "new_distance": 0.0,
            "payload": None,
        }

        converged_pass: int | None = None
        # |V| - 1 relaxation passes over the stable edge list.
        for i in range(1, len(nodes)):
            payload = {"pass": i}
            if mode == "snapshot":
                payload = {"pass": i, "distances": dict(dist)}
            yield {
                "kind": "visit",
                "node": None,
                "edge": None,
                "old_distance": None,
                "new_distance": None,
                "payload": payload,
            }

            relaxations = 0
            for u, v, w in edges:
                if dist[u] == float("inf"):
                    continue
                new_dist = dist[u] + w
                if new_dist < dist[v]:
                    old_dist = dist[v]
                    dist[v] = new_dist
                    prev[v] = u
                    relax_payload = None
                    if mode == "snapshot":
                        relax_payload = {"distances": dict(dist)}
                    yield {
                        "kind": "relax",
                        "node": v,
                        "edge": (u, v),
                        "old_distance": old_dist,
                        "new_distance": new_dist,
                        "payload": relax_payload,
                    }
                    relaxations += 1
                else:
                    yield {
                        "kind": "skip",
                        "node": v,
                        "edge": (u, v),
                        "old_distance": dist[v],
                        "new_distance": new_dist,
                        "payload": {"reason": "worse"},
                    }

            if relaxations == 0:
                converged_pass = i
                break

        # Detection pass only runs after a full n-1 passes without early convergence.
        if converged_pass is None:
            for u, v, w in edges:
                if dist[u] == float("inf"):
                    continue
                if dist[u] + w < dist[v]:
                    payload = {"negative_cycle": True}
                    if not graph.directed:
                        # Every undirected negative edge is a two-node negative
                        # cycle, so on the default graph type the bare message
                        # reads like a solver failure; explain the way out.
                        payload["message"] = (
                            "Negative cycle detected: in an undirected graph every "
                            "negative edge forms a two-node negative cycle. Switch "
                            "to Directed mode to explore negative weights."
                        )
                    yield {
                        "kind": "final",
                        "node": target,
                        "edge": None,
                        "old_distance": None,
                        "new_distance": None,
                        "payload": payload,
                    }
                    return

        if target is not None:
            final_distance = dist.get(target, float("inf"))
            reason = "target_found" if final_distance < float("inf") else "unreachable"
            payload = {"reason": reason}
            if converged_pass is not None:
                payload["converged_at_pass"] = converged_pass
            yield {
                "kind": "final",
                "node": target,
                "edge": None,
                "old_distance": None,
                "new_distance": final_distance,
                "payload": payload,
            }


try:
    register_algorithm(BellmanFordAlgorithm.spec, BellmanFordAlgorithm)
except ValueError:
    pass
