from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .base import AlgorithmStep


@dataclass
class AlgorithmState:
    distances: dict[str, float]
    visited: list[str] = field(default_factory=list)
    payload: dict = field(default_factory=dict)
    last_step: AlgorithmStep | None = None


def init_state(nodes: Iterable[str]) -> AlgorithmState:
    return AlgorithmState(distances={node: float("inf") for node in nodes})


def apply_step(state: AlgorithmState, step: AlgorithmStep) -> None:
    state.last_step = step
    payload = step.get("payload")
    if payload:
        state.payload.update(payload)

    kind = step.get("kind")
    if kind == "visit":
        node = step.get("node")
        if node is not None:
            state.visited.append(node)
    elif kind == "relax":
        node = step.get("node")
        new_distance = step.get("new_distance")
        if node is not None and new_distance is not None:
            state.distances[node] = new_distance


def apply_steps(steps: Iterable[AlgorithmStep], nodes: Iterable[str]) -> AlgorithmState:
    state = init_state(nodes)
    for step in steps:
        apply_step(state, step)
    return state
