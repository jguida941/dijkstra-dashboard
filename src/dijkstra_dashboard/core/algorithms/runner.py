from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .base import AlgorithmOutput, AlgorithmResult, AlgorithmStep
from ..errors import AlgorithmError


@dataclass
class AlgorithmState:
    distances: dict[str, float]
    visited: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    last_step: AlgorithmStep | None = None
    prev: dict[str, str] = field(default_factory=dict)
    current: str | None = None
    touched_edges: set[tuple[str, str]] = field(default_factory=set)


def init_state(nodes: Iterable[str]) -> AlgorithmState:
    return AlgorithmState(distances={node: float("inf") for node in nodes})


def apply_step(state: AlgorithmState, step: AlgorithmStep) -> None:
    state.last_step = step
    payload = step.get("payload")
    if payload:
        state.payload.update(payload)

    edge = step.get("edge")
    if edge is not None:
        state.touched_edges.add(tuple(edge))

    kind = step.get("kind")
    if kind == "visit":
        node = step.get("node")
        if node is not None:
            state.visited.append(node)
            state.current = node
            new_distance = step.get("new_distance")
            if new_distance is not None:
                state.distances[node] = new_distance
    elif kind == "relax":
        node = step.get("node")
        new_distance = step.get("new_distance")
        if node is not None and new_distance is not None:
            state.distances[node] = new_distance
        if edge is not None and node is not None:
            state.prev[node] = edge[0]


def apply_steps(steps: Iterable[AlgorithmStep], nodes: Iterable[str]) -> AlgorithmState:
    state = init_state(nodes)
    for step in steps:
        apply_step(state, step)
    return state


def build_paths(prev: dict[str, str], start: str,
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


def result_from_steps(steps: Iterable[AlgorithmStep], nodes: Iterable[str], start: str,
                      target: str | None,
                      kind: AlgorithmOutput = "single_path") -> AlgorithmResult:
    state = apply_steps(steps, nodes)
    if state.payload.get("negative_cycle"):
        raise AlgorithmError("Negative cycle detected.")

    paths = build_paths(state.prev, start, state.distances)
    if target is None:
        path = []
        distance = None
    else:
        path = paths.get(target, [])
        distance = state.distances.get(target, float("inf"))

    return AlgorithmResult(
        kind=kind,
        path=path,
        distance=distance,
        distances=state.distances,
        paths=paths,
        visited_order=state.visited,
        steps=None,
    )
