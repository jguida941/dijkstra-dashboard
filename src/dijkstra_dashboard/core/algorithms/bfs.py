from __future__ import annotations

from collections import deque
from typing import Iterable

from .base import AlgorithmParam, AlgorithmResult, AlgorithmSpec, AlgorithmStep, PathfindingAlgorithm
from .registry import register_algorithm
from .runner import result_from_steps
from ..errors import AlgorithmError
from ..graph import Graph


class BreadthFirstSearchAlgorithm(PathfindingAlgorithm):
    spec = AlgorithmSpec(
        name="bfs",
        description="Fewest-hops path (ignores weights)",
        inputs=[
            AlgorithmParam(name="start", type="node_id", required=True),
            AlgorithmParam(name="target", type="node_id", required=False),
        ],
        output_kind="single_path",
        constraints={"ignores_weights": True},
    )
    pseudocode = [
        "function bfs(graph, start, target):",
        "  for each node v: hops[v] = ∞",
        "  hops[start] = 0",
        "  queue = [start]  (FIFO)",
        "  while queue is not empty:",
        "    u = queue.pop_front()",
        "    settle u",
        "    if u = target: break",
        "    for each neighbor v of u:",
        "      if v already seen: skip edge",
        "      else: hops[v] = hops[u] + 1; prev[v] = u; enqueue v",
        "  return hops, prev",
    ]
    step_line_map = {
        ("visit", None): [5, 6],
        ("relax", None): [8, 10],
        ("skip", "visited"): [8, 9],
        ("final", "target_found"): [7, 11],
        ("final", "unreachable"): [1, 11],
        ("final", None): [11],
    }

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

        adjacency = graph.to_adjacency_dict()
        if start not in adjacency:
            raise AlgorithmError(f"Start node '{start}' not found.")

        # Hop counts double as distances; a node is "seen" once its hop count is finite.
        hops = {node: float("inf") for node in adjacency}
        prev: dict[str, str] = {}
        hops[start] = 0
        queue: deque[str] = deque([start])

        while queue:
            current = queue.popleft()

            payload = None
            if mode == "snapshot":
                payload = {"distances": dict(hops), "frontier": list(queue)}

            yield {
                "kind": "visit",
                "node": current,
                "edge": None,
                "old_distance": None,
                "new_distance": hops[current],
                "payload": payload,
            }

            if target is not None and current == target:
                break

            for neighbor, _weight in adjacency[current]:
                if hops[neighbor] == float("inf"):
                    old_dist = hops[neighbor]
                    hops[neighbor] = hops[current] + 1
                    prev[neighbor] = current
                    relax_payload = None
                    if mode == "snapshot":
                        relax_payload = {"distances": dict(hops)}
                    yield {
                        "kind": "relax",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": old_dist,
                        "new_distance": hops[neighbor],
                        "payload": relax_payload,
                    }
                else:
                    yield {
                        "kind": "skip",
                        "node": neighbor,
                        "edge": (current, neighbor),
                        "old_distance": hops[neighbor],
                        "new_distance": hops[current] + 1,
                        "payload": {"reason": "visited"},
                    }
                    continue
                queue.append(neighbor)

        if target is not None:
            final_distance = hops.get(target, float("inf"))
            reason = "target_found" if final_distance < float("inf") else "unreachable"
            yield {
                "kind": "final",
                "node": target,
                "edge": None,
                "old_distance": None,
                "new_distance": final_distance,
                "payload": {"reason": reason},
            }


try:
    register_algorithm(BreadthFirstSearchAlgorithm.spec, BreadthFirstSearchAlgorithm)
except ValueError:
    pass
